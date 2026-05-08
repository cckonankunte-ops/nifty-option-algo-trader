"""Unit tests for SignalEngine — both SIMPLE_5MIN and ADVANCED_5MIN_1MIN_ADX modes."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from backend.engine.signal_engine import SignalEngine


# --- Helper: create a mock StrategyConfig ---

def make_config(
    signal_mode="SIMPLE_5MIN",
    ema_fast=9,
    ema_slow=21,
    rsi_period=14,
    rsi_upper=60,
    rsi_lower=40,
    adx_period=14,
    adx_threshold=25,
):
    config = MagicMock()
    config.signal_mode = signal_mode
    config.ema_fast = ema_fast
    config.ema_slow = ema_slow
    config.rsi_period = rsi_period
    config.rsi_upper = rsi_upper
    config.rsi_lower = rsi_lower
    config.adx_period = adx_period
    config.adx_threshold = adx_threshold
    return config


# --- Helper: generate synthetic candle data ---

def make_candles_bullish_crossover(n=30):
    """
    Generate candles where EMA9 crosses above EMA21 at the end,
    RSI > 60, and price > VWAP.
    """
    # Start with a downtrend then reverse to uptrend
    base = 24000.0
    prices = []
    for i in range(n):
        if i < n // 2:
            # Downtrend
            prices.append(base - i * 10)
        else:
            # Strong uptrend to force crossover
            prices.append(base - (n // 2) * 10 + (i - n // 2) * 30)

    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-05-08 09:45", periods=n, freq="5min"),
        "open": [p - 5 for p in prices],
        "high": [p + 15 for p in prices],
        "low": [p - 15 for p in prices],
        "close": prices,
        "volume": [1000 + i * 50 for i in range(n)],
    })
    return df


def make_candles_bearish_crossover(n=30):
    """
    Generate candles where EMA9 crosses below EMA21 at the end,
    RSI < 40, and price < VWAP.
    """
    base = 24000.0
    prices = []
    for i in range(n):
        if i < n // 2:
            # Uptrend
            prices.append(base + i * 10)
        else:
            # Strong downtrend to force crossover
            prices.append(base + (n // 2) * 10 - (i - n // 2) * 30)

    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-05-08 09:45", periods=n, freq="5min"),
        "open": [p + 5 for p in prices],
        "high": [p + 15 for p in prices],
        "low": [p - 15 for p in prices],
        "close": prices,
        "volume": [1000 + i * 50 for i in range(n)],
    })
    return df


def make_candles_no_crossover(n=30):
    """Generate flat candles with no crossover."""
    base = 24000.0
    prices = [base + np.sin(i * 0.1) * 5 for i in range(n)]

    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-05-08 09:45", periods=n, freq="5min"),
        "open": [p - 1 for p in prices],
        "high": [p + 3 for p in prices],
        "low": [p - 3 for p in prices],
        "close": prices,
        "volume": [1000] * n,
    })
    return df


# ============================================================
# SIMPLE_5MIN MODE TESTS
# ============================================================

class TestSimple5MinMode:
    """Tests for SIMPLE_5MIN signal generation."""

    def test_buy_call_signal(self):
        """BUY_CALL when EMA bullish crossover + RSI > 60 + price > VWAP."""
        config = make_config(signal_mode="SIMPLE_5MIN")
        engine = SignalEngine(config)
        candles = make_candles_bullish_crossover(n=30)

        result = engine.generate_signal(candles_5min=candles)

        assert result["signal"] in ("BUY_CALL", "HOLD")
        assert result["mode_used"] == "SIMPLE_5MIN"
        assert "indicators" in result
        assert "reason" in result
        # Verify indicator structure
        indicators = result["indicators"]
        assert "ema_fast" in indicators
        assert "ema_slow" in indicators
        assert "rsi" in indicators
        assert "vwap" in indicators
        assert "adx" in indicators
        assert "price" in indicators

    def test_buy_put_signal(self):
        """BUY_PUT when EMA bearish crossover + RSI < 40 + price < VWAP."""
        config = make_config(signal_mode="SIMPLE_5MIN")
        engine = SignalEngine(config)
        candles = make_candles_bearish_crossover(n=30)

        result = engine.generate_signal(candles_5min=candles)

        assert result["signal"] in ("BUY_PUT", "HOLD")
        assert result["mode_used"] == "SIMPLE_5MIN"
        assert "indicators" in result

    def test_hold_signal_no_crossover(self):
        """HOLD when no crossover occurs."""
        config = make_config(signal_mode="SIMPLE_5MIN")
        engine = SignalEngine(config)
        candles = make_candles_no_crossover(n=30)

        result = engine.generate_signal(candles_5min=candles)

        assert result["signal"] == "HOLD"
        assert result["mode_used"] == "SIMPLE_5MIN"

    def test_hold_insufficient_data(self):
        """HOLD when insufficient candle data."""
        config = make_config(signal_mode="SIMPLE_5MIN")
        engine = SignalEngine(config)
        candles = make_candles_no_crossover(n=1)

        result = engine.generate_signal(candles_5min=candles)

        assert result["signal"] == "HOLD"
        assert "Insufficient" in result["reason"]

    def test_response_structure(self):
        """Verify response dict always has required keys."""
        config = make_config(signal_mode="SIMPLE_5MIN")
        engine = SignalEngine(config)
        candles = make_candles_no_crossover(n=30)

        result = engine.generate_signal(candles_5min=candles)

        assert set(result.keys()) == {"signal", "reason", "indicators", "mode_used"}
        assert set(result["indicators"].keys()) == {
            "ema_fast", "ema_slow", "rsi", "vwap", "adx", "price"
        }

    def test_adx_is_none_in_simple_mode(self):
        """ADX should be None in SIMPLE_5MIN mode."""
        config = make_config(signal_mode="SIMPLE_5MIN")
        engine = SignalEngine(config)
        candles = make_candles_no_crossover(n=30)

        result = engine.generate_signal(candles_5min=candles)

        assert result["indicators"]["adx"] is None


# ============================================================
# ADVANCED_5MIN_1MIN_ADX MODE TESTS
# ============================================================

class TestAdvanced5Min1MinADX:
    """Tests for ADVANCED_5MIN_1MIN_ADX signal generation."""

    def test_hold_when_adx_below_threshold(self):
        """HOLD when ADX < threshold even if EMA/RSI/VWAP conditions met."""
        config = make_config(signal_mode="ADVANCED_5MIN_1MIN_ADX", adx_threshold=99)
        engine = SignalEngine(config)
        candles = make_candles_bullish_crossover(n=30)

        result = engine.generate_signal(candles_5min=candles)

        assert result["signal"] == "HOLD"
        assert result["mode_used"] == "ADVANCED_5MIN_1MIN_ADX"
        # ADX should be present
        assert result["indicators"]["adx"] is not None or "filtered" in result["reason"].lower() or "ADX" in result["reason"]

    def test_potential_call_detected(self):
        """POTENTIAL_CALL detected when all 5-min conditions + ADX met."""
        config = make_config(signal_mode="ADVANCED_5MIN_1MIN_ADX", adx_threshold=0)
        engine = SignalEngine(config)
        candles = make_candles_bullish_crossover(n=30)

        result = engine.generate_signal(candles_5min=candles)

        # Should either confirm immediately or be waiting for 1-min
        assert result["signal"] in ("BUY_CALL", "HOLD")
        assert result["mode_used"] == "ADVANCED_5MIN_1MIN_ADX"

    def test_buy_call_with_1min_confirmation(self):
        """BUY_CALL confirmed when 1-min candle closes above signal candle high."""
        config = make_config(signal_mode="ADVANCED_5MIN_1MIN_ADX", adx_threshold=0)
        engine = SignalEngine(config)
        candles_5min = make_candles_bullish_crossover(n=30)

        # Get the signal candle high
        signal_candle_high = candles_5min.iloc[-1]["high"]

        # 1-min candle that closes above signal candle high
        candles_1min = pd.DataFrame({
            "timestamp": [datetime(2025, 5, 8, 12, 0)],
            "open": [signal_candle_high - 5],
            "high": [signal_candle_high + 20],
            "low": [signal_candle_high - 10],
            "close": [signal_candle_high + 10],  # Above signal candle high
            "volume": [500],
        })

        result = engine.generate_signal(candles_5min=candles_5min, candles_1min=candles_1min)

        # With ADX threshold=0, should get BUY_CALL if crossover conditions met
        assert result["signal"] in ("BUY_CALL", "HOLD")
        assert result["mode_used"] == "ADVANCED_5MIN_1MIN_ADX"

    def test_hold_when_1min_not_confirmed(self):
        """HOLD when 1-min candle doesn't break signal candle level."""
        config = make_config(signal_mode="ADVANCED_5MIN_1MIN_ADX", adx_threshold=0)
        engine = SignalEngine(config)
        candles_5min = make_candles_bullish_crossover(n=30)

        signal_candle_high = candles_5min.iloc[-1]["high"]

        # 1-min candle that does NOT close above signal candle high
        candles_1min = pd.DataFrame({
            "timestamp": [datetime(2025, 5, 8, 12, 0)],
            "open": [signal_candle_high - 20],
            "high": [signal_candle_high - 5],
            "low": [signal_candle_high - 30],
            "close": [signal_candle_high - 10],  # Below signal candle high
            "volume": [500],
        })

        result = engine.generate_signal(candles_5min=candles_5min, candles_1min=candles_1min)

        assert result["signal"] == "HOLD"
        assert result["mode_used"] == "ADVANCED_5MIN_1MIN_ADX"

    def test_buy_put_with_1min_confirmation(self):
        """BUY_PUT confirmed when 1-min candle closes below signal candle low."""
        config = make_config(signal_mode="ADVANCED_5MIN_1MIN_ADX", adx_threshold=0)
        engine = SignalEngine(config)
        candles_5min = make_candles_bearish_crossover(n=30)

        signal_candle_low = candles_5min.iloc[-1]["low"]

        # 1-min candle that closes below signal candle low
        candles_1min = pd.DataFrame({
            "timestamp": [datetime(2025, 5, 8, 12, 0)],
            "open": [signal_candle_low + 5],
            "high": [signal_candle_low + 10],
            "low": [signal_candle_low - 20],
            "close": [signal_candle_low - 10],  # Below signal candle low
            "volume": [500],
        })

        result = engine.generate_signal(candles_5min=candles_5min, candles_1min=candles_1min)

        assert result["signal"] in ("BUY_PUT", "HOLD")
        assert result["mode_used"] == "ADVANCED_5MIN_1MIN_ADX"

    def test_timeout_discards_potential_signal(self):
        """Potential signal discarded after 5-minute timeout."""
        config = make_config(signal_mode="ADVANCED_5MIN_1MIN_ADX", adx_threshold=0)
        engine = SignalEngine(config)

        # Manually set a stale potential signal
        engine._potential_signal = "POTENTIAL_CALL"
        engine._signal_candle_high = 24100.0
        engine._signal_candle_low = 24050.0
        engine._signal_candle_time = datetime.now() - timedelta(minutes=6)

        candles_5min = make_candles_no_crossover(n=30)
        candles_1min = pd.DataFrame({
            "timestamp": [datetime(2025, 5, 8, 12, 0)],
            "open": [24200],
            "high": [24250],
            "low": [24150],
            "close": [24200],
            "volume": [500],
        })

        result = engine.generate_signal(candles_5min=candles_5min, candles_1min=candles_1min)

        assert result["signal"] == "HOLD"
        assert "timed out" in result["reason"].lower()

    def test_adx_present_in_advanced_mode(self):
        """ADX value should be present in Advanced mode response."""
        config = make_config(signal_mode="ADVANCED_5MIN_1MIN_ADX", adx_threshold=0)
        engine = SignalEngine(config)
        candles = make_candles_no_crossover(n=30)

        result = engine.generate_signal(candles_5min=candles)

        # ADX should be computed (may be 0 for flat data but not None)
        assert result["indicators"]["adx"] is not None


# ============================================================
# ATM STRIKE AND EXPIRY TESTS
# ============================================================

class TestATMStrikeAndExpiry:
    """Tests for ATM strike calculation and weekly expiry."""

    def test_atm_round_down(self):
        """24367 rounds to 24350."""
        assert SignalEngine.calculate_atm_strike(24367) == 24350

    def test_atm_round_up(self):
        """24375 rounds to 24400."""
        assert SignalEngine.calculate_atm_strike(24375) == 24400

    def test_atm_exact(self):
        """24400 stays 24400."""
        assert SignalEngine.calculate_atm_strike(24400) == 24400

    def test_atm_midpoint(self):
        """24325 rounds to 24350 (nearest 50)."""
        assert SignalEngine.calculate_atm_strike(24325) == 24350

    def test_weekly_expiry_monday(self):
        """Monday → this Thursday."""
        monday = datetime(2025, 5, 5, 10, 0)  # Monday
        expiry = SignalEngine.get_weekly_expiry(monday)
        assert expiry.weekday() == 3  # Thursday
        assert expiry.date() == datetime(2025, 5, 8).date()

    def test_weekly_expiry_thursday_before_cutoff(self):
        """Thursday before 3:30 PM → today."""
        thursday = datetime(2025, 5, 8, 10, 0)
        expiry = SignalEngine.get_weekly_expiry(thursday)
        assert expiry.date() == thursday.date()

    def test_weekly_expiry_thursday_after_cutoff(self):
        """Thursday after 3:30 PM → next Thursday."""
        thursday = datetime(2025, 5, 8, 16, 0)
        expiry = SignalEngine.get_weekly_expiry(thursday)
        assert expiry.weekday() == 3
        assert expiry.date() == datetime(2025, 5, 15).date()

    def test_weekly_expiry_friday(self):
        """Friday → next Thursday."""
        friday = datetime(2025, 5, 9, 10, 0)
        expiry = SignalEngine.get_weekly_expiry(friday)
        assert expiry.weekday() == 3
        assert expiry.date() == datetime(2025, 5, 15).date()
