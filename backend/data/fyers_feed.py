"""Fyers Data Feed — WebSocket ticks and REST candle fetching."""

import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Callable

import pandas as pd

logger = logging.getLogger(__name__)

NIFTY_SYMBOL = "NSE:NIFTY50-INDEX"
RECONNECT_INTERVAL = 30  # seconds


class FyersFeed:
    """Manages live tick data and historical candle fetching from Fyers."""

    def __init__(self, fyers_client=None, on_tick: Optional[Callable] = None):
        """
        Args:
            fyers_client: Fyers API client instance
            on_tick: Callback function called with each tick dict
        """
        self.fyers = fyers_client
        self.on_tick = on_tick
        self._last_tick_price: Optional[float] = None
        self._last_tick_time: Optional[datetime] = None
        self._connected = False
        self._ws = None
        self._reconnect_task: Optional[asyncio.Task] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_last_tick_price(self) -> Optional[float]:
        """Return the most recent tick price."""
        return self._last_tick_price

    async def connect(self):
        """Connect to Fyers WebSocket for live Nifty ticks."""
        if self.fyers is None:
            logger.warning("No Fyers client — running in offline mode")
            return

        try:
            from fyers_apiv3 import fyersModel

            data_type = "SymbolUpdate"
            symbols = [NIFTY_SYMBOL]

            self._ws = fyersModel.FyersDataSocket(
                access_token=self.fyers.token,
                log_path="",
                litemode=False,
                write_to_file=False,
                reconnect=True,
                on_connect=self._on_ws_connect,
                on_close=self._on_ws_close,
                on_error=self._on_ws_error,
                on_message=self._on_ws_message,
            )
            self._ws.subscribe(symbols=symbols, data_type=data_type)
            self._ws.keep_running()
            self._connected = True
            logger.info("Fyers WebSocket connected")

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self._connected = False
            self._schedule_reconnect()

    async def disconnect(self):
        """Gracefully disconnect WebSocket."""
        if self._ws:
            try:
                self._ws.unsubscribe(symbols=[NIFTY_SYMBOL])
                self._ws.close_connection()
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")
        self._connected = False

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

    def _on_ws_connect(self):
        """WebSocket connected callback."""
        self._connected = True
        logger.info("WebSocket connected")

    def _on_ws_close(self):
        """WebSocket closed callback."""
        self._connected = False
        logger.warning("WebSocket disconnected")
        self._schedule_reconnect()

    def _on_ws_error(self, error):
        """WebSocket error callback."""
        logger.error(f"WebSocket error: {error}")

    def _on_ws_message(self, message):
        """Process incoming tick data."""
        try:
            if isinstance(message, dict):
                ltp = message.get("ltp") or message.get("last_price")
                if ltp:
                    self._last_tick_price = float(ltp)
                    self._last_tick_time = datetime.now()
                    if self.on_tick:
                        self.on_tick({
                            "price": self._last_tick_price,
                            "timestamp": self._last_tick_time,
                            "symbol": NIFTY_SYMBOL,
                        })
        except Exception as e:
            logger.error(f"Error processing tick: {e}")

    def _schedule_reconnect(self):
        """Schedule reconnection attempt."""
        try:
            loop = asyncio.get_event_loop()
            self._reconnect_task = loop.create_task(self._reconnect_loop())
        except RuntimeError:
            logger.warning("No event loop for reconnect scheduling")

    async def _reconnect_loop(self):
        """Attempt reconnection every 30 seconds."""
        while not self._connected:
            logger.info(f"Attempting WebSocket reconnect in {RECONNECT_INTERVAL}s...")
            await asyncio.sleep(RECONNECT_INTERVAL)
            await self.connect()

    def fetch_candles_5min(self, symbol: str = NIFTY_SYMBOL, count: int = 50) -> pd.DataFrame:
        """
        Fetch historical 5-minute candles via REST API.

        Args:
            symbol: Fyers symbol
            count: Number of candles to fetch

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        return self._fetch_candles(symbol, resolution="5", count=count)

    def fetch_candles_1min(self, symbol: str = NIFTY_SYMBOL, count: int = 30) -> pd.DataFrame:
        """
        Fetch historical 1-minute candles via REST API.
        Only called when mode is ADVANCED_5MIN_1MIN_ADX.

        Args:
            symbol: Fyers symbol
            count: Number of candles to fetch

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        return self._fetch_candles(symbol, resolution="1", count=count)

    def fetch_historical_candles(
        self,
        symbol: str,
        resolution: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch historical candles with automatic 100-day pagination.

        Args:
            symbol: Fyers symbol
            resolution: "1" or "5"
            start_date: "YYYY-MM-DD"
            end_date: "YYYY-MM-DD"

        Returns:
            Concatenated DataFrame of all candles in range
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        all_candles = []
        current_start = start

        while current_start < end:
            current_end = min(current_start + timedelta(days=99), end)

            data = {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "1",
                "range_from": current_start.strftime("%Y-%m-%d"),
                "range_to": current_end.strftime("%Y-%m-%d"),
                "cont_flag": "1",
            }

            try:
                if self.fyers:
                    response = self.fyers.history(data=data)
                    if response.get("s") == "ok" and response.get("candles"):
                        all_candles.extend(response["candles"])
            except Exception as e:
                logger.error(f"Error fetching candles {current_start} to {current_end}: {e}")

            current_start = current_end + timedelta(days=1)

        if not all_candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        return df

    def _fetch_candles(self, symbol: str, resolution: str, count: int) -> pd.DataFrame:
        """Internal method to fetch recent candles."""
        if self.fyers is None:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        end = datetime.now()
        # Estimate start based on resolution and count
        minutes = int(resolution) * count * 2  # extra buffer
        start = end - timedelta(minutes=minutes)

        data = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "1",
            "range_from": start.strftime("%Y-%m-%d"),
            "range_to": end.strftime("%Y-%m-%d"),
            "cont_flag": "1",
        }

        try:
            response = self.fyers.history(data=data)
            if response.get("s") == "ok" and response.get("candles"):
                df = pd.DataFrame(
                    response["candles"],
                    columns=["timestamp", "open", "high", "low", "close", "volume"],
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                return df.tail(count)
        except Exception as e:
            logger.error(f"Error fetching {resolution}-min candles: {e}")

        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
