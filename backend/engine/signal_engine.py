"""Signal Engine — generates BUY CALL / BUY PUT / HOLD signals.

Supports two modes:
- SIMPLE_5MIN: EMA crossover + RSI + VWAP on 5-min candles
- ADVANCED_5MIN_1MIN_ADX: 5-min trend + ADX filter + 1-min entry confirmation
"""

from datetime import datetime, timedelta, time as dtime
from typing import Optional
import pandas as pd
import pandas_ta as ta


class SignalEngine:
    """Trading signal generator with dual-mode support."""

    def __init__(self, config):
        """
        Initialize with a StrategyConfig object (or dict-like with attributes).

        Args:
            config: StrategyConfig with ema_fast, ema_slow, rsi_period,
                    rsi_upper, rsi_lower, adx_period, adx_threshold, signal_mode
        """
        self.config = config
        self.mode = getattr(config, "signal_mode", "SIMPLE_5MIN")

        # State for Advanced mode potential signal tracking
        self._potential_signal: Optional[str] = None  # POTENTIAL_CALL or POTENTIAL_PUT
        self._signal_candle_high: Optional[float] = None
        self._signal_candle_low: Optional[float] = None
        self._signal_candle_time: Optional[datetime] = None

    def generate_signal(
        self,
        candles_5min: pd.DataFrame,
        candles_1min: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        Generate a trading signal based on the active mode.

        Args:
            candles_5min: DataFrame with columns [timestamp, open, high, low, close, volume]
            candles_1min: DataFrame (same columns), required for ADVANCED mode

        Returns:
            dict with keys: signal, reason, indicators, mode_used
        """
        if self.mode == "ADVANCED_5MIN_1MIN_ADX":
            return self._check_advanced_signal(candles_5min, candles_1min)
        return self._check_simple_signal(candles_5min)

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute EMA, RSI, VWAP on a candle DataFrame."""
        df = df.copy()

        ema_fast = getattr(self.config, "ema_fast", 9)
        ema_slow = getattr(self.config, "ema_slow", 21)
        rsi_period = getattr(self.config, "rsi_period", 14)

        # EMA
        df["ema_fast"] = ta.ema(df["close"], length=ema_fast)
        df["ema_slow"] = ta.ema(df["close"], length=ema_slow)

        # RSI
        df["rsi"] = ta.rsi(df["close"], length=rsi_period)

        # VWAP — cumulative typical_price * volume / cumulative volume
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

        return df

    def _check_simple_signal(self, candles_5min: pd.DataFrame) -> dict:
        """MODE A: Simple 5-min signal logic."""
        df = self._compute_indicators(candles_5min)

        if len(df) < 2:
            return self._build_response("HOLD", "Insufficient candle data", df)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        ema_fast_val = curr["ema_fast"]
        ema_slow_val = curr["ema_slow"]
        rsi_val = curr["rsi"]
        vwap_val = curr["vwap"]
        price = curr["close"]

        rsi_upper = getattr(self.config, "rsi_upper", 60)
        rsi_lower = getattr(self.config, "rsi_lower", 40)

        # Check for EMA crossover
        bullish_crossover = (
            ema_fast_val > ema_slow_val and prev["ema_fast"] <= prev["ema_slow"]
        )
        bearish_crossover = (
            ema_fast_val < ema_slow_val and prev["ema_fast"] >= prev["ema_slow"]
        )

        signal = "HOLD"
        reason = "No crossover or conflicting conditions"

        # Log indicator values for debugging
        if bullish_crossover or bearish_crossover:
            import logging
            logging.getLogger(__name__).info(
                f"Crossover detected! bullish={bullish_crossover}, bearish={bearish_crossover}, "
                f"RSI={rsi_val:.1f}, price={price:.2f}, VWAP={vwap_val:.2f}"
            )

        if bullish_crossover and rsi_val > rsi_upper and price > vwap_val:
            signal = "BUY_CALL"
            reason = (
                f"EMA{getattr(self.config, 'ema_fast', 9)} crossed above "
                f"EMA{getattr(self.config, 'ema_slow', 21)}, "
                f"RSI={rsi_val:.1f} > {rsi_upper}, price={price:.2f} > VWAP={vwap_val:.2f}"
            )
        elif bearish_crossover and rsi_val < rsi_lower and price < vwap_val:
            signal = "BUY_PUT"
            reason = (
                f"EMA{getattr(self.config, 'ema_fast', 9)} crossed below "
                f"EMA{getattr(self.config, 'ema_slow', 21)}, "
                f"RSI={rsi_val:.1f} < {rsi_lower}, price={price:.2f} < VWAP={vwap_val:.2f}"
            )

        return self._build_response(signal, reason, df)

    def _check_advanced_signal(
        self,
        candles_5min: pd.DataFrame,
        candles_1min: Optional[pd.DataFrame] = None,
    ) -> dict:
        """MODE B: Advanced 5-min + 1-min + ADX signal logic."""
        df = self._compute_indicators(candles_5min)

        # Compute ADX
        adx_period = getattr(self.config, "adx_period", 14)
        adx_threshold = getattr(self.config, "adx_threshold", 25)

        adx_df = ta.adx(df["high"], df["low"], df["close"], length=adx_period)
        if adx_df is not None and f"ADX_{adx_period}" in adx_df.columns:
            df["adx"] = adx_df[f"ADX_{adx_period}"]
        else:
            df["adx"] = 0.0

        if len(df) < 2:
            return self._build_response("HOLD", "Insufficient candle data", df, include_adx=True)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        adx_val = curr["adx"] if pd.notna(curr["adx"]) else 0.0
        rsi_upper = getattr(self.config, "rsi_upper", 60)
        rsi_lower = getattr(self.config, "rsi_lower", 40)

        # Step 1: Check if we already have a pending potential signal
        if self._potential_signal is not None:
            return self._check_1min_confirmation(candles_1min, df)

        # Step 1: 5-min trend detection
        ema_fast_val = curr["ema_fast"]
        ema_slow_val = curr["ema_slow"]
        rsi_val = curr["rsi"]
        vwap_val = curr["vwap"]
        price = curr["close"]

        bullish_crossover = (
            ema_fast_val > ema_slow_val and prev["ema_fast"] <= prev["ema_slow"]
        )
        bearish_crossover = (
            ema_fast_val < ema_slow_val and prev["ema_fast"] >= prev["ema_slow"]
        )

        if bullish_crossover and rsi_val > rsi_upper and price > vwap_val and adx_val >= adx_threshold:
            self._potential_signal = "POTENTIAL_CALL"
            self._signal_candle_high = curr["high"]
            self._signal_candle_low = curr["low"]
            self._signal_candle_time = datetime.now()

            # Immediately check 1-min if available
            if candles_1min is not None and len(candles_1min) > 0:
                return self._check_1min_confirmation(candles_1min, df)

            return self._build_response(
                "HOLD",
                f"POTENTIAL_CALL detected, waiting for 1-min confirmation above {self._signal_candle_high:.2f}",
                df,
                include_adx=True,
            )

        elif bearish_crossover and rsi_val < rsi_lower and price < vwap_val and adx_val >= adx_threshold:
            self._potential_signal = "POTENTIAL_PUT"
            self._signal_candle_high = curr["high"]
            self._signal_candle_low = curr["low"]
            self._signal_candle_time = datetime.now()

            if candles_1min is not None and len(candles_1min) > 0:
                return self._check_1min_confirmation(candles_1min, df)

            return self._build_response(
                "HOLD",
                f"POTENTIAL_PUT detected, waiting for 1-min confirmation below {self._signal_candle_low:.2f}",
                df,
                include_adx=True,
            )

        # ADX too low or no crossover
        if (bullish_crossover or bearish_crossover) and adx_val < adx_threshold:
            reason = f"Crossover detected but ADX={adx_val:.1f} < threshold={adx_threshold}, filtered out"
        else:
            reason = "No crossover or conflicting conditions"

        return self._build_response("HOLD", reason, df, include_adx=True)

    def _check_1min_confirmation(
        self, candles_1min: Optional[pd.DataFrame], df_5min: pd.DataFrame
    ) -> dict:
        """Check 1-min candle for entry confirmation."""
        # Check timeout (5 minutes from signal candle)
        if self._signal_candle_time is not None:
            elapsed = (datetime.now() - self._signal_candle_time).total_seconds()
            if elapsed > 300:  # 5 minutes
                self._reset_potential()
                return self._build_response(
                    "HOLD",
                    "Potential signal timed out (5-min window expired)",
                    df_5min,
                    include_adx=True,
                )

        if candles_1min is None or len(candles_1min) == 0:
            return self._build_response(
                "HOLD",
                f"Waiting for 1-min candle data for {self._potential_signal} confirmation",
                df_5min,
                include_adx=True,
            )

        latest_1min = candles_1min.iloc[-1]

        if self._potential_signal == "POTENTIAL_CALL":
            if latest_1min["close"] > self._signal_candle_high:
                signal = "BUY_CALL"
                reason = (
                    f"1-min candle closed at {latest_1min['close']:.2f} "
                    f"above signal candle high {self._signal_candle_high:.2f}"
                )
                self._reset_potential()
                return self._build_response(signal, reason, df_5min, include_adx=True)

        elif self._potential_signal == "POTENTIAL_PUT":
            if latest_1min["close"] < self._signal_candle_low:
                signal = "BUY_PUT"
                reason = (
                    f"1-min candle closed at {latest_1min['close']:.2f} "
                    f"below signal candle low {self._signal_candle_low:.2f}"
                )
                self._reset_potential()
                return self._build_response(signal, reason, df_5min, include_adx=True)

        return self._build_response(
            "HOLD",
            f"Waiting for 1-min confirmation for {self._potential_signal}",
            df_5min,
            include_adx=True,
        )

    def _reset_potential(self):
        """Clear potential signal state."""
        self._potential_signal = None
        self._signal_candle_high = None
        self._signal_candle_low = None
        self._signal_candle_time = None

    def _build_response(
        self, signal: str, reason: str, df: pd.DataFrame, include_adx: bool = False
    ) -> dict:
        """Build the standard signal response dictionary."""
        indicators = {
            "ema_fast": None,
            "ema_slow": None,
            "rsi": None,
            "vwap": None,
            "adx": None,
            "price": None,
        }

        if len(df) > 0:
            last = df.iloc[-1]
            indicators["ema_fast"] = float(last["ema_fast"]) if pd.notna(last.get("ema_fast")) else None
            indicators["ema_slow"] = float(last["ema_slow"]) if pd.notna(last.get("ema_slow")) else None
            indicators["rsi"] = float(last["rsi"]) if pd.notna(last.get("rsi")) else None
            indicators["vwap"] = float(last["vwap"]) if pd.notna(last.get("vwap")) else None
            indicators["price"] = float(last["close"]) if pd.notna(last.get("close")) else None
            if include_adx and "adx" in last.index:
                indicators["adx"] = float(last["adx"]) if pd.notna(last.get("adx")) else None

        return {
            "signal": signal,
            "reason": reason,
            "indicators": indicators,
            "mode_used": self.mode,
        }

    @staticmethod
    def calculate_atm_strike(spot_price: float) -> int:
        """
        Calculate ATM strike by rounding to nearest multiple of 50.

        Examples:
            spot = 24367 → ATM = 24350
            spot = 24375 → ATM = 24400
        """
        return int(round(spot_price / 50) * 50)

    @staticmethod
    def get_weekly_expiry(current_time: Optional[datetime] = None) -> datetime:
        """
        Determine current weekly expiry (nearest upcoming Thursday).

        If today is Thursday after 3:30 PM IST, use next Thursday.
        """
        if current_time is None:
            current_time = datetime.now()

        weekday = current_time.weekday()  # Monday=0, Thursday=3

        if weekday < 3:
            # Before Thursday — this Thursday
            days_ahead = 3 - weekday
        elif weekday == 3:
            # Thursday — check time
            cutoff = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
            if current_time <= cutoff:
                days_ahead = 0  # Today is expiry
            else:
                days_ahead = 7  # Next Thursday
        else:
            # After Thursday — next Thursday
            days_ahead = 3 + (7 - weekday)

        expiry = current_time + timedelta(days=days_ahead)
        return expiry.replace(hour=15, minute=30, second=0, microsecond=0)
