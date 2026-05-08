"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, JSON
)
from backend.database import Base


class StrategyConfig(Base):
    """Strategy configuration model."""

    __tablename__ = "strategy_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, default="Default")
    is_active = Column(Boolean, default=True)

    # Signal mode
    signal_mode = Column(String(50), default="SIMPLE_5MIN")

    # EMA settings
    ema_fast = Column(Integer, default=9)
    ema_slow = Column(Integer, default=21)

    # RSI settings
    rsi_period = Column(Integer, default=14)
    rsi_upper = Column(Integer, default=60)
    rsi_lower = Column(Integer, default=40)

    # ADX settings (Advanced mode)
    adx_period = Column(Integer, default=14)
    adx_threshold = Column(Integer, default=25)

    # Risk settings
    sl_percent = Column(Float, default=3.0)
    trailing_sl_trigger = Column(Float, default=4.0)
    trailing_sl_trail = Column(Float, default=2.0)
    daily_loss_cap_percent = Column(Float, default=6.0)
    fund_per_trade_percent = Column(Float, default=25.0)

    # Trading window
    trading_start_time = Column(String(10), default="09:45")
    trading_end_time = Column(String(10), default="15:00")

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Trade(Base):
    """Trade record model."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False)
    strike = Column(Integer, nullable=False)
    option_type = Column(String(2), nullable=False)  # CE or PE

    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)

    signal_used = Column(JSON, nullable=True)  # indicator values at entry
    sl_price = Column(Float, nullable=True)
    peak_price = Column(Float, nullable=True)  # for trailing SL tracking

    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)

    status = Column(String(20), default="OPEN")  # OPEN, CLOSED, SQUARED_OFF
    exit_reason = Column(String(30), nullable=True)  # SL_HIT, TRAILING_SL, SQUARE_OFF, TARGET
    trigger_type = Column(String(30), nullable=True)  # direct_signal, 1min_confirmed

    created_at = Column(DateTime, default=datetime.utcnow)


class BacktestResult(Base):
    """Backtest result model."""

    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    run_name = Column(String(100), nullable=True)
    run_date = Column(DateTime, default=datetime.utcnow)

    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(Float, nullable=True)

    signal_mode = Column(String(50), nullable=True)

    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    avg_profit = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    total_return_percent = Column(Float, default=0.0)

    adx_filtered_count = Column(Integer, default=0)

    equity_curve_data = Column(JSON, nullable=True)
    trade_log = Column(JSON, nullable=True)
    config_snapshot = Column(JSON, nullable=True)


class OrderLog(Base):
    """Order log for tracking all order attempts."""

    __tablename__ = "order_logs"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(Integer, nullable=True)
    order_type = Column(String(10), nullable=False)  # BUY or SELL
    symbol = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=True)

    status = Column(String(20), nullable=False)  # SUBMITTED, FILLED, FAILED
    broker_response = Column(JSON, nullable=True)
    trading_mode = Column(String(10), nullable=False)  # paper or live

    created_at = Column(DateTime, default=datetime.utcnow)


class DailySummary(Base):
    """Daily trading summary."""

    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), nullable=False, unique=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    total_pnl_percent = Column(Float, default=0.0)
    daily_cap_hit = Column(Boolean, default=False)
    signal_mode_used = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
