"""Backtest Runner — runs historical strategy backtests."""

import logging
from datetime import datetime
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
            dict with metrics, equity_curve, trade_log, adx_filtered_count
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

        # Fetch historical candles with pagination
        candles_5min = self._fetch_candles_paginated(start_date, end_date, "5")
        candles_1min = None
        if signal_mode == "ADVANCED_5MIN_1MIN_ADX":
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

        return {
            "metrics": metrics,
            "equity_curve": equity_curve,
            "trade_log": trade_log,
        }

    def _fetch_candles_paginated(self, start_date: str, end_date: str, resolution: str) -> pd.DataFrame:
        """Fetch candles with 100-day pagination via Dhan."""
        from backend.data.dhan_feed import DhanFeed, NIFTY_INDEX_SECURITY_ID
        from backend.config import settings
        feed = DhanFeed(client_id=settings.DHAN_CLIENT_ID, access_token=settings.DHAN_ACCESS_TOKEN)
        return feed.fetch_nifty_spot_candles_5min(start_date, end_date)

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
