"""Dhan Data Feed — instrument master, WebSocket ticks, and REST candle fetching."""

import logging
import threading
import time
import io
from datetime import datetime, date, timedelta
from typing import Optional, Callable, Dict, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

NIFTY_INDEX_SECURITY_ID = "13"
INSTRUMENT_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
RECONNECT_INTERVAL = 30


class DhanFeed:
    """Manages instrument master, live ticks, and historical candles via DhanHQ."""

    def __init__(self, client_id: str, access_token: str, on_tick: Optional[Callable] = None):
        """
        Args:
            client_id: Dhan client ID
            access_token: Dhan access token
            on_tick: Callback for each tick {security_id, price, timestamp}
        """
        self.client_id = client_id
        self.access_token = access_token
        self.on_tick = on_tick

        # Instrument master: (strike, expiry_date, option_type) → security_id
        self.instrument_master: Dict[Tuple[float, date, str], str] = {}
        self._master_loaded_at: Optional[datetime] = None

        # Last tick prices: security_id → price
        self._last_tick: Dict[str, float] = {}

        # WebSocket state
        self._feed = None
        self._feed_thread: Optional[threading.Thread] = None
        self._subscribed_ids: list = []
        self._connected = False

        # Dhan client for REST calls
        try:
            from dhanhq import DhanContext, dhanhq as DhanHQ
            dhan_context = DhanContext(client_id, access_token)
            self.dhan = DhanHQ(dhan_context)
        except ImportError:
            # Older SDK version without DhanContext
            try:
                from dhanhq import dhanhq as DhanHQ
                self.dhan = DhanHQ(client_id, access_token)
            except Exception as e:
                logger.error(f"Failed to initialize Dhan client (old SDK): {e}")
                self.dhan = None
        except Exception as e:
            logger.error(f"Failed to initialize Dhan client: {e}")
            self.dhan = None

    # ─── Instrument Master ───────────────────────────────────────────

    def load_instrument_master(self) -> bool:
        """
        Download and parse Dhan instrument master CSV.
        Filters for Nifty options and builds security_id lookup.

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            import urllib.request

            logger.info("Downloading Dhan instrument master CSV...")
            response = urllib.request.urlopen(INSTRUMENT_MASTER_URL)
            csv_data = response.read().decode("utf-8")

            df = pd.read_csv(io.StringIO(csv_data))

            # Filter for NSE Nifty options
            mask = (
                (df["SEM_EXM_EXCH_ID"] == "NSE")
                & (df["SEM_INSTRUMENT_NAME"] == "OPTIDX")
                & (df["SEM_TRADING_SYMBOL"].str.contains("NIFTY", na=False))
            )
            nifty_options = df[mask].copy()

            # Build lookup dict
            self.instrument_master.clear()
            for _, row in nifty_options.iterrows():
                try:
                    strike = float(row["SEM_STRIKE_PRICE"])
                    expiry = pd.to_datetime(row["SEM_EXPIRY_DATE"]).date()
                    # Determine option type from trading symbol
                    symbol = str(row["SEM_TRADING_SYMBOL"])
                    if symbol.endswith("CE"):
                        opt_type = "CE"
                    elif symbol.endswith("PE"):
                        opt_type = "PE"
                    else:
                        continue

                    security_id = str(row["SEM_SMST_SECURITY_ID"])
                    self.instrument_master[(strike, expiry, opt_type)] = security_id
                except (ValueError, KeyError):
                    continue

            self._master_loaded_at = datetime.now()
            logger.info(f"Instrument master loaded: {len(self.instrument_master)} Nifty option instruments")
            return True

        except Exception as e:
            logger.critical(f"Failed to load instrument master: {e}")
            return False

    def get_security_id(self, strike: float, expiry_date: date, option_type: str) -> str:
        """
        Look up security_id from instrument master.

        Raises:
            ValueError if not found
        """
        key = (strike, expiry_date, option_type)
        sid = self.instrument_master.get(key)
        if sid is None:
            raise ValueError(
                f"Security ID not found for NIFTY {int(strike)}{option_type} "
                f"expiry {expiry_date}. Instrument master may need refresh."
            )
        return sid

    @property
    def is_master_loaded(self) -> bool:
        return len(self.instrument_master) > 0

    @property
    def master_loaded_at(self) -> Optional[datetime]:
        return self._master_loaded_at

    # ─── WebSocket Live Feed ─────────────────────────────────────────

    def start_feed(self, security_ids: list) -> None:
        """Subscribe to live tick data for given security_ids."""
        self._subscribed_ids = security_ids

        try:
            from dhanhq import marketfeed

            instruments = [
                (marketfeed.NSE_FNO, sid, marketfeed.Ticker)
                for sid in security_ids
            ]

            self._feed = marketfeed.DhanFeed(
                client_id=self.client_id,
                access_token=self.access_token,
                instruments=instruments,
                subscription_code=marketfeed.Ticker,
                on_message=self._on_tick_message,
                on_close=self._on_feed_close,
            )

            self._feed_thread = threading.Thread(target=self._feed.run_forever, daemon=True)
            self._feed_thread.start()
            self._connected = True
            logger.info(f"Dhan WebSocket feed started for {len(security_ids)} instruments")

        except Exception as e:
            logger.error(f"Failed to start Dhan feed: {e}")
            self._connected = False

    def _on_tick_message(self, message: dict) -> None:
        """Process incoming tick data."""
        try:
            security_id = str(message.get("security_id", ""))
            ltp = message.get("LTP") or message.get("ltp")

            if security_id and ltp:
                price = float(ltp)
                self._last_tick[security_id] = price

                if self.on_tick:
                    self.on_tick({
                        "security_id": security_id,
                        "price": price,
                        "timestamp": datetime.now(),
                    })
        except Exception as e:
            logger.error(f"Error processing Dhan tick: {e}")

    def _on_feed_close(self) -> None:
        """Handle feed disconnection."""
        self._connected = False
        logger.warning("Dhan WebSocket disconnected")
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Schedule reconnection in background."""
        thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        thread.start()

    def _reconnect_loop(self) -> None:
        """Attempt reconnection every 30 seconds."""
        while not self._connected:
            logger.info(f"Attempting Dhan feed reconnect in {RECONNECT_INTERVAL}s...")
            time.sleep(RECONNECT_INTERVAL)
            self.start_feed(self._subscribed_ids)

    def stop_feed(self) -> None:
        """Disconnect WebSocket feed."""
        if self._feed:
            try:
                self._feed.disconnect()
            except Exception as e:
                logger.error(f"Error stopping Dhan feed: {e}")
        self._connected = False
        logger.info("Dhan feed stopped")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_last_price(self, security_id: str) -> Optional[float]:
        """Return last known tick price for security_id."""
        price = self._last_tick.get(security_id)
        if price is None and self.dhan:
            # Fallback to REST quote
            try:
                quote = self.dhan.get_market_quote(
                    security_id=security_id,
                    exchange_segment="NSE_FNO"
                )
                if quote and quote.get("data"):
                    price = float(quote["data"].get("LTP", 0))
                    self._last_tick[security_id] = price
            except Exception as e:
                logger.error(f"REST quote fallback failed: {e}")
        return price

    # ─── REST Historical Candles ─────────────────────────────────────

    def fetch_nifty_spot_candles_5min(self, from_date: str, to_date: str) -> pd.DataFrame:
        """
        Fetch 5-min candles for Nifty INDEX (for signal engine EMA/RSI/VWAP).

        Args:
            from_date: "YYYY-MM-DD"
            to_date: "YYYY-MM-DD"
        """
        return self._fetch_historical_range(
            security_id=NIFTY_INDEX_SECURITY_ID,
            exchange_segment="NSE_EQ",
            instrument_type="INDEX",
            interval="5",
            from_date=from_date,
            to_date=to_date,
        )

    def fetch_candles_5min(self, security_id: str, from_date: str, to_date: str) -> pd.DataFrame:
        """Fetch 5-min candles for an option security_id."""
        return self._fetch_historical_range(
            security_id=security_id,
            exchange_segment="NSE_FNO",
            instrument_type="OPTIDX",
            interval="5",
            from_date=from_date,
            to_date=to_date,
        )

    def fetch_candles_1min(self, security_id: str, from_date: str, to_date: str) -> pd.DataFrame:
        """Fetch 1-min candles for an option security_id (last 30 rows)."""
        df = self._fetch_historical_range(
            security_id=security_id,
            exchange_segment="NSE_FNO",
            instrument_type="OPTIDX",
            interval="1",
            from_date=from_date,
            to_date=to_date,
        )
        return df.tail(30)

    def _fetch_historical_range(
        self,
        security_id: str,
        exchange_segment: str,
        instrument_type: str,
        interval: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """Fetch historical candles by iterating day-by-day (intraday_minute_data supports max 5 days)."""
        if self.dhan is None:
            logger.warning("Dhan client not initialized — cannot fetch historical data")
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        from datetime import date as date_type
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        all_candles = []

        # Iterate in 5-day chunks (Dhan intraday_minute_data supports max 5 days)
        current_start = start
        while current_start <= end:
            current_end = min(current_start + timedelta(days=4), end)

            try:
                logger.info(f"Fetching chunk: {current_start} to {current_end}")

                response = self.dhan.intraday_minute_data(
                    security_id=security_id,
                    exchange_segment=exchange_segment,
                    instrument_type=instrument_type,
                    from_date=current_start.strftime("%Y-%m-%d"),
                    to_date=current_end.strftime("%Y-%m-%d"),
                )

                # Log raw response for debugging
                if response:
                    data = response.get("data", {})
                    if isinstance(data, dict):
                        candle_count = len(data.get("open", []))
                        if candle_count == 0:
                            # Try historical_daily_data as fallback
                            logger.debug(f"intraday_minute_data returned 0 candles, trying historical_daily_data")
                            response = self.dhan.historical_daily_data(
                                security_id=security_id,
                                exchange_segment=exchange_segment,
                                instrument_type=instrument_type,
                                from_date=current_start.strftime("%Y-%m-%d"),
                                to_date=current_end.strftime("%Y-%m-%d"),
                            )
                            logger.info(f"historical_daily_data response: status={response.get('status')}, data_keys={list(response.get('data', {}).keys()) if isinstance(response.get('data'), dict) else type(response.get('data'))}")

                if response and response.get("status") == "success" and response.get("data"):
                    data = response["data"]

                    if isinstance(data, dict) and "open" in data:
                        timestamps = data.get("timestamp", data.get("start_Time", []))
                        opens = data.get("open", [])
                        highs = data.get("high", [])
                        lows = data.get("low", [])
                        closes = data.get("close", [])
                        volumes = data.get("volume", [0] * len(opens))

                        if len(opens) > 0:
                            logger.info(f"Got {len(opens)} candles for {current_start} to {current_end}")

                        for i in range(len(opens)):
                            all_candles.append({
                                "timestamp": timestamps[i] if i < len(timestamps) else None,
                                "open": opens[i],
                                "high": highs[i],
                                "low": lows[i],
                                "close": closes[i],
                                "volume": volumes[i] if i < len(volumes) else 0,
                            })
                    elif isinstance(data, list) and len(data) > 0:
                        all_candles.extend(data)
                else:
                    remarks = response.get("remarks", "") if response else ""
                    logger.debug(f"No data for {current_start} to {current_end}: {remarks}")

            except Exception as e:
                logger.error(f"Error fetching candles {current_start} to {current_end}: {e}")

            current_start = current_end + timedelta(days=1)

        if not all_candles:
            logger.warning(f"No candle data fetched for security_id={security_id} ({from_date} to {to_date})")
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(all_candles)
        logger.info(f"Total candles fetched: {len(df)}")

        # Normalize column names
        col_map = {"start_Time": "timestamp", "start_time": "timestamp"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        for col in ["timestamp", "open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0

        if len(df) > 0 and df["timestamp"].notna().any():
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
            # If epoch conversion failed, try direct parsing
            if df["timestamp"].isna().all():
                df["timestamp"] = pd.to_datetime(all_candles[0]["timestamp"], errors="coerce")
                if pd.isna(df["timestamp"].iloc[0]):
                    df["timestamp"] = pd.to_datetime([c["timestamp"] for c in all_candles], errors="coerce")

            df = df.dropna(subset=["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)

        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def _fetch_historical(
        self,
        security_id: str,
        exchange_segment: str,
        instrument_type: str,
        interval: int,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """Fetch historical candles with 100-day pagination."""
        if self.dhan is None:
            logger.warning("Dhan client not initialized — cannot fetch historical data")
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
        all_candles = []

        current_start = start
        while current_start <= end:
            current_end = min(current_start + timedelta(days=99), end)

            try:
                # Dhan SDK method for intraday historical data
                response = self.dhan.intraday_daily_minute_charts(
                    security_id=security_id,
                    exchange_segment=exchange_segment,
                    instrument_type=instrument_type,
                )

                if response and response.get("status") == "success" and response.get("data"):
                    data = response["data"]
                    # Dhan returns: {"open": [...], "high": [...], "low": [...], "close": [...], "volume": [...], "start_Time": [...]}
                    if isinstance(data, dict) and "open" in data:
                        timestamps = data.get("start_Time", data.get("timestamp", []))
                        for i in range(len(data["open"])):
                            candle = {
                                "timestamp": timestamps[i] if i < len(timestamps) else None,
                                "open": data["open"][i],
                                "high": data["high"][i],
                                "low": data["low"][i],
                                "close": data["close"][i],
                                "volume": data["volume"][i] if "volume" in data else 0,
                            }
                            all_candles.append(candle)
                    elif isinstance(data, list):
                        all_candles.extend(data)
                else:
                    logger.warning(f"Dhan API returned no data for {security_id} ({current_start} to {current_end}): {response}")

            except Exception as e:
                logger.error(f"Error fetching candles {current_start} to {current_end}: {e}")

            current_start = current_end + timedelta(days=1)

        if not all_candles:
            logger.warning(f"No candle data fetched for security_id={security_id}")
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(all_candles)

        # Normalize column names (Dhan uses start_Time)
        col_map = {"start_Time": "timestamp", "start_time": "timestamp"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # Ensure required columns exist
        for col in ["timestamp", "open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0

        if "timestamp" in df.columns and len(df) > 0:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)

            # Filter to requested date range
            df = df[(df["timestamp"] >= pd.Timestamp(from_date)) & (df["timestamp"] <= pd.Timestamp(to_date) + timedelta(days=1))]

        return df[["timestamp", "open", "high", "low", "close", "volume"]]
