"""Candle Builder — aggregates live ticks into OHLCV candles."""

from datetime import datetime, timedelta
from typing import Optional
from collections import deque

import pandas as pd


class CandleBuilder:
    """Aggregates tick data into time-based OHLCV candles."""

    def __init__(self, interval_minutes: int = 5, max_candles: int = 100):
        """
        Args:
            interval_minutes: Candle interval in minutes (default 5)
            max_candles: Maximum completed candles to keep in memory
        """
        self.interval = timedelta(minutes=interval_minutes)
        self.max_candles = max_candles

        # Completed candles storage
        self._candles_5min: deque = deque(maxlen=max_candles)
        self._candles_1min: deque = deque(maxlen=max_candles * 5)

        # Current building candle (5-min)
        self._current_5min: Optional[dict] = None
        self._current_5min_start: Optional[datetime] = None

        # Current building candle (1-min)
        self._current_1min: Optional[dict] = None
        self._current_1min_start: Optional[datetime] = None

    def on_tick(self, tick: dict):
        """
        Process a new tick and aggregate into candles.

        Args:
            tick: dict with keys: price, timestamp, volume (optional)
        """
        price = tick["price"]
        timestamp = tick.get("timestamp", datetime.now())
        volume = tick.get("volume", 1)

        self._update_candle(price, timestamp, volume, interval_min=5)
        self._update_candle(price, timestamp, volume, interval_min=1)

    def _update_candle(self, price: float, timestamp: datetime, volume: int, interval_min: int):
        """Update the appropriate candle (5-min or 1-min)."""
        interval = timedelta(minutes=interval_min)

        if interval_min == 5:
            current = self._current_5min
            current_start = self._current_5min_start
        else:
            current = self._current_1min
            current_start = self._current_1min_start

        # Check if we need a new candle
        if current is None or (current_start and timestamp >= current_start + interval):
            # Save completed candle
            if current is not None:
                if interval_min == 5:
                    self._candles_5min.append(current)
                else:
                    self._candles_1min.append(current)

            # Start new candle
            # Align to interval boundary
            minute = timestamp.minute
            aligned_minute = (minute // interval_min) * interval_min
            candle_start = timestamp.replace(minute=aligned_minute, second=0, microsecond=0)

            current = {
                "timestamp": candle_start,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }
            if interval_min == 5:
                self._current_5min = current
                self._current_5min_start = candle_start
            else:
                self._current_1min = current
                self._current_1min_start = candle_start
        else:
            # Update existing candle
            current["high"] = max(current["high"], price)
            current["low"] = min(current["low"], price)
            current["close"] = price
            current["volume"] += volume

    def get_candles(self, count: int = 50) -> pd.DataFrame:
        """
        Get last N completed 5-minute candles as DataFrame.

        Args:
            count: Number of candles to return

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        candles = list(self._candles_5min)[-count:]
        if not candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(candles)

    def get_1min_candles(self, count: int = 30) -> pd.DataFrame:
        """
        Get last N completed 1-minute candles as DataFrame.

        Args:
            count: Number of candles to return

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        candles = list(self._candles_1min)[-count:]
        if not candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(candles)

    @property
    def candle_count_5min(self) -> int:
        """Number of completed 5-min candles."""
        return len(self._candles_5min)

    @property
    def candle_count_1min(self) -> int:
        """Number of completed 1-min candles."""
        return len(self._candles_1min)
