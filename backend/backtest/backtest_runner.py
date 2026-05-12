"""Backtest Runner — runs historical strategy backtests."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import MagicMock

import pandas as pd
import numpy as np

from backend.engine.signal_engine import SignalEngine

logger = logging.getLogger(__name__)


class BacktestRunner:
    """Runs backtests using historical candle data and the SignalEngine."""

    def __init__(self):
        """Initialize backtest runner (uses Dhan feed internally)."""
        pass

    def run(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float,
        signal_mode: str = "SIMPLE_5MIN",
        candle_interval: str = "daily",
        ema_fast: int = 9,
        ema_slow: int = 21,
        rsi_period: int = 14,
        rsi_upper: int = 50,
        rsi_lower: int = 50,
        adx_period: int = 14,
        adx_threshold: int = 25,
        sl_percent: float = 3.0,
        trailing_sl_trigger: float = 4.0,
        trailing_sl_trail: float = 2.0,
    ) -> dict:
        """
        Run a backtest over the specified date range.

        Returns:
            dict with metrics, equity_curve, trade_log, daily_pnl, adx_filtered_count
        """
        # Build config mock
        config = MagicMock()
        config.signal_mode = signal_mode
        config.ema_fast = ema_fast
        config.ema_slow = ema_slow
        config.rsi_period = rsi_period
        config.rsi_upper = rsi_upper
        config.rsi_lower = rsi_lower
        config.adx_period = adx_period
        config.adx_threshold = adx_threshold

        engine = SignalEngine(config)

        # Fetch historical candles based on selected interval
        candles_5min = self._fetch_candles_paginated(start_date, end_date, candle_interval)
        candles_1min = None
        if signal_mode == "ADVANCED_5MIN_1MIN_ADX" and candle_interval != "1":
            candles_1min = self._fetch_candles_paginated(start_date, end_date, "1")

        if candles_5min.empty:
            return self._empty_result(initial_capital, signal_mode)

        # Run backtest simulation
        capital = initial_capital
        position = None
        trade_log = []
        equity_curve = []
        adx_filtered_count = 0
        sl_pct = max(sl_percent, 3.0)

        # Iterate through candles
        # Need at least ema_slow + 2 candles for crossover detection
        lookback = ema_slow + 2

        for i in range(lookback, len(candles_5min)):
            window_5min = candles_5min.iloc[max(0, i - lookback):i + 1].copy()
            current_candle = candles_5min.iloc[i]
            current_price = current_candle["close"]

            # Update equity curve
            unrealized = 0
            if position:
                unrealized = (current_price - position["entry_price"]) * position["quantity"]
            equity_curve.append({
                "timestamp": str(current_candle["timestamp"]),
                "value": capital + unrealized,
            })

            # Check exit conditions for open position
            if position:
                # Check stop loss
                if current_price <= position["sl_price"]:
                    pnl = (position["sl_price"] - position["entry_price"]) * position["quantity"]
                    capital += pnl
                    trade_log.append({
                        **position,
                        "exit_price": position["sl_price"],
                        "exit_time": str(current_candle["timestamp"]),
                        "pnl": pnl,
                        "exit_reason": "SL_HIT",
                    })
                    position = None
                    continue

                # Check trailing SL
                if current_price > position.get("peak_price", position["entry_price"]):
                    position["peak_price"] = current_price

                profit_pct = ((position["peak_price"] - position["entry_price"]) / position["entry_price"]) * 100
                if profit_pct >= trailing_sl_trigger:
                    trailing_sl = position["peak_price"] * (1 - trailing_sl_trail / 100)
                    if trailing_sl > position["sl_price"]:
                        position["sl_price"] = trailing_sl

                    if current_price <= position["sl_price"]:
                        pnl = (position["sl_price"] - position["entry_price"]) * position["quantity"]
                        capital += pnl
                        trade_log.append({
                            **position,
                            "exit_price": position["sl_price"],
                            "exit_time": str(current_candle["timestamp"]),
                            "pnl": pnl,
                            "exit_reason": "TRAILING_SL",
                        })
                        position = None
                        continue

                continue  # Skip signal check if position open

            # Generate signal
            window_1min = None
            if candles_1min is not None and not candles_1min.empty:
                # Get 1-min candles around current 5-min candle timestamp
                ts = current_candle["timestamp"]
                mask = candles_1min["timestamp"] <= ts
                window_1min = candles_1min[mask].tail(30).copy()

            result = engine.generate_signal(
                candles_5min=window_5min,
                candles_1min=window_1min,
            )

            signal = result["signal"]

            # Log every signal check for debugging
            indicators = result.get("indicators", {})
            logger.debug(
                f"Candle {i}: signal={signal}, "
                f"ema_fast={indicators.get('ema_fast')}, ema_slow={indicators.get('ema_slow')}, "
                f"rsi={indicators.get('rsi')}, price={indicators.get('price')}, vwap={indicators.get('vwap')}"
            )

            # Log first few signals at INFO level for visibility
            if i < lookback + 5 or signal != "HOLD":
                logger.info(
                    f"[Backtest] Candle {i}/{len(candles_5min)}: signal={signal}, reason={result.get('reason', '')[:80]}"
                )

            # Track ADX filtered signals
            if signal_mode == "ADVANCED_5MIN_1MIN_ADX" and "filtered" in result.get("reason", "").lower():
                adx_filtered_count += 1

            if signal in ("BUY_CALL", "BUY_PUT"):
                # Enter position
                entry_price = current_price
                quantity = 25  # 1 lot for backtest simplicity
                sl_price = entry_price * (1 - sl_pct / 100)

                trigger_type = "direct_signal" if signal_mode == "SIMPLE_5MIN" else "1min_confirmed"

                position = {
                    "entry_price": entry_price,
                    "entry_time": str(current_candle["timestamp"]),
                    "quantity": quantity,
                    "signal": signal,
                    "sl_price": sl_price,
                    "peak_price": entry_price,
                    "trigger_type": trigger_type,
                }

        # Close any remaining position at end
        if position:
            final_price = candles_5min.iloc[-1]["close"]
            pnl = (final_price - position["entry_price"]) * position["quantity"]
            capital += pnl
            trade_log.append({
                **position,
                "exit_price": final_price,
                "exit_time": str(candles_5min.iloc[-1]["timestamp"]),
                "pnl": pnl,
                "exit_reason": "BACKTEST_END",
            })

        # Compute metrics
        metrics = self._compute_metrics(trade_log, initial_capital, capital, equity_curve)
        metrics["adx_filtered_count"] = adx_filtered_count
        metrics["signal_mode"] = signal_mode
        metrics["candle_interval"] = candle_interval

        # Compute daily P&L from trade log
        daily_pnl = self._compute_daily_pnl(trade_log)

        return {
            "metrics": metrics,
            "equity_curve": equity_curve,
            "trade_log": trade_log,
            "daily_pnl": daily_pnl,
        }

    def _fetch_candles_paginated(self, start_date: str, end_date: str, resolution: str) -> pd.DataFrame:
        """Fetch candles. Daily uses index, 5min/1min uses monthly futures contracts from Dhan."""
        if resolution == "daily":
            from backend.data.dhan_feed import DhanFeed
            from backend.config import settings
            feed = DhanFeed(client_id=settings.DHAN_CLIENT_ID, access_token=settings.DHAN_ACCESS_TOKEN)
            return feed.fetch_nifty_spot_candles_5min(start_date, end_date)
        else:
            # Use dynamic monthly futures contracts for intraday
            return self._fetch_monthly_futures_intraday(start_date, end_date, resolution)

    def _fetch_monthly_futures_intraday(self, start_date: str, end_date: str, interval: str) -> pd.DataFrame:
        """
        Fetch intraday data using the correct monthly Nifty futures contract for each month.
        Jan dates → Jan futures, Feb dates → Feb futures, etc.
        """
        import time
        from backend.data.dhan_feed import DhanFeed
        from backend.config import settings

        feed = DhanFeed(client_id=settings.DHAN_CLIENT_ID, access_token=settings.DHAN_ACCESS_TOKEN)

        # Load instrument master to find futures contracts
        if not feed.is_master_loaded:
            feed.load_instrument_master()

        # Find all NIFTY FUTIDX contracts from master
        nifty_futures = self._get_nifty_futures_map(feed)

        if not nifty_futures:
            logger.warning("No Nifty futures contracts found in instrument master")
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        all_candles = []

        # Iterate month by month
        current = start
        while current <= end:
            # Find the futures contract for this month
            month_key = (current.year, current.month)
            security_id = nifty_futures.get(month_key)

            if not security_id:
                # Try next month's contract (near month)
                next_month = current.month + 1 if current.month < 12 else 1
                next_year = current.year if current.month < 12 else current.year + 1
                security_id = nifty_futures.get((next_year, next_month))

            if not security_id:
                logger.warning(f"No futures contract found for {current.strftime('%b %Y')}")
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    current = current.replace(month=current.month + 1, day=1)
                continue

            # Determine date range for this month
            month_start = max(current, start)
            if current.month == 12:
                month_end_date = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end_date = current.replace(month=current.month + 1, day=1) - timedelta(days=1)
            month_end = min(month_end_date, end)

            logger.info(f"Fetching {current.strftime('%b %Y')} futures (sid={security_id}) from {month_start.strftime('%Y-%m-%d')} to {month_end.strftime('%Y-%m-%d')}")

            # Fetch in 5-day chunks with rate limiting
            chunk_start = month_start
            while chunk_start <= month_end:
                chunk_end = min(chunk_start + timedelta(days=4), month_end)

                try:
                    time.sleep(1)  # Rate limit
                    from_dt = chunk_start.strftime("%Y-%m-%d") + " 09:15:00"
                    to_dt = chunk_end.strftime("%Y-%m-%d") + " 15:30:00"

                    response = feed.dhan.intraday_minute_data(
                        security_id=security_id,
                        exchange_segment="NSE_FNO",
                        instrument_type="FUTIDX",
                        from_date=from_dt,
                        to_date=to_dt,
                        interval=interval,
                    )

                    if response and response.get("status") == "success" and response.get("data"):
                        data = response["data"]
                        if isinstance(data, dict) and "open" in data:
                            opens = data.get("open", [])
                            if len(opens) > 0:
                                timestamps = data.get("timestamp", [])
                                highs = data.get("high", [])
                                lows = data.get("low", [])
                                closes = data.get("close", [])
                                volumes = data.get("volume", [0] * len(opens))

                                for i in range(len(opens)):
                                    all_candles.append({
                                        "timestamp": timestamps[i] if i < len(timestamps) else None,
                                        "open": opens[i],
                                        "high": highs[i],
                                        "low": lows[i],
                                        "close": closes[i],
                                        "volume": volumes[i] if i < len(volumes) else 0,
                                    })

                                logger.info(f"  Got {len(opens)} candles for {chunk_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")

                except Exception as e:
                    logger.error(f"Error fetching {chunk_start} to {chunk_end}: {e}")

                chunk_start = chunk_end + timedelta(days=1)

            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)

        if not all_candles:
            logger.warning(f"No intraday futures data fetched for {start_date} to {end_date}")
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(all_candles)
        logger.info(f"Total intraday candles stitched: {len(df)}")

        # Convert timestamps
        if len(df) > 0:
            sample = df["timestamp"].iloc[0]
            if isinstance(sample, (int, float)) and sample > 1_000_000_000:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            else:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)

        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def _get_nifty_futures_map(self, feed) -> dict:
        """
        Build a map of (year, month) → security_id for NIFTY futures from instrument master.
        """
        import urllib.request
        import io

        futures_map = {}

        try:
            csv_url = "https://images.dhan.co/api-data/api-scrip-master.csv"
            response = urllib.request.urlopen(csv_url)
            csv_data = response.read().decode("utf-8")
            master = pd.read_csv(io.StringIO(csv_data))

            # Filter NIFTY futures only (not BANKNIFTY, FINNIFTY etc)
            nifty_fut = master[
                (master["SEM_EXM_EXCH_ID"] == "NSE") &
                (master["SEM_INSTRUMENT_NAME"] == "FUTIDX") &
                (master["SEM_TRADING_SYMBOL"].str.match(r"^NIFTY-", na=False))
            ]

            for _, row in nifty_fut.iterrows():
                try:
                    expiry = pd.to_datetime(row["SEM_EXPIRY_DATE"])
                    security_id = str(row["SEM_SMST_SECURITY_ID"])
                    # Map to expiry month (contract expires in that month)
                    futures_map[(expiry.year, expiry.month)] = security_id
                    logger.info(f"  Found: {row['SEM_TRADING_SYMBOL']} → sid={security_id}, expiry={expiry.date()}")
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error loading futures map: {e}")

        return futures_map

    def _compute_daily_pnl(self, trade_log: list) -> list:
        """Compute daily P&L from trade log for bar chart visualization."""
        if not trade_log:
            return []

        daily = {}
        for trade in trade_log:
            exit_time = trade.get("exit_time", "")
            if exit_time:
                day = exit_time[:10]  # "YYYY-MM-DD"
                if day not in daily:
                    daily[day] = 0.0
                daily[day] += trade.get("pnl", 0)

        return [{"date": k, "pnl": round(v, 2)} for k, v in sorted(daily.items())]

    def _compute_metrics(self, trade_log: list, initial_capital: float, final_capital: float, equity_curve: list) -> dict:
        """Compute backtest performance metrics."""
        total_trades = len(trade_log)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "total_return_percent": 0.0,
                "initial_capital": initial_capital,
                "final_capital": final_capital,
            }

        profits = [t["pnl"] for t in trade_log if t["pnl"] > 0]
        losses = [t["pnl"] for t in trade_log if t["pnl"] <= 0]

        winning_trades = len(profits)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        avg_profit = np.mean(profits) if profits else 0.0
        avg_loss = np.mean(losses) if losses else 0.0

        # Max drawdown from equity curve
        max_drawdown = 0.0
        if equity_curve:
            values = [e["value"] for e in equity_curve]
            peak = values[0]
            for v in values:
                if v > peak:
                    peak = v
                dd = ((peak - v) / peak) * 100
                if dd > max_drawdown:
                    max_drawdown = dd

        # Sharpe ratio (simplified — daily returns)
        total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100
        returns = [t["pnl"] / initial_capital for t in trade_log]
        sharpe = 0.0
        if len(returns) > 1:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                sharpe = (mean_ret / std_ret) * np.sqrt(252)

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "avg_profit": round(float(avg_profit), 2),
            "avg_loss": round(float(avg_loss), 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(float(sharpe), 2),
            "total_return_percent": round(total_return_pct, 2),
            "initial_capital": initial_capital,
            "final_capital": round(final_capital, 2),
        }

    def _empty_result(self, initial_capital: float, signal_mode: str) -> dict:
        """Return empty result when no data available."""
        return {
            "metrics": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "total_return_percent": 0.0,
                "initial_capital": initial_capital,
                "final_capital": initial_capital,
                "adx_filtered_count": 0,
                "signal_mode": signal_mode,
            },
            "equity_curve": [],
            "trade_log": [],
        }
