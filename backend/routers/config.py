"""Config router — /api/config endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from backend.database import get_db

router = APIRouter(prefix="/api/config", tags=["config"])

VALID_SIGNAL_MODES = ["SIMPLE_5MIN", "ADVANCED_5MIN_1MIN_ADX"]


class StrategyConfigUpdate(BaseModel):
    signal_mode: Optional[str] = None
    ema_fast: Optional[int] = None
    ema_slow: Optional[int] = None
    rsi_period: Optional[int] = None
    rsi_upper: Optional[int] = None
    rsi_lower: Optional[int] = None
    adx_period: Optional[int] = None
    adx_threshold: Optional[int] = None
    sl_percent: Optional[float] = None
    trailing_sl_trigger: Optional[float] = None
    trailing_sl_trail: Optional[float] = None
    daily_loss_cap_percent: Optional[float] = None
    fund_per_trade_percent: Optional[float] = None


@router.get("")
async def get_config(db=Depends(get_db)):
    """Get active strategy config."""
    from backend.models import StrategyConfig

    config = db.query(StrategyConfig).filter(StrategyConfig.is_active == True).first()
    if not config:
        return {"message": "No active config found"}

    return {
        "id": config.id,
        "name": config.name,
        "signal_mode": config.signal_mode,
        "ema_fast": config.ema_fast,
        "ema_slow": config.ema_slow,
        "rsi_period": config.rsi_period,
        "rsi_upper": config.rsi_upper,
        "rsi_lower": config.rsi_lower,
        "adx_period": config.adx_period,
        "adx_threshold": config.adx_threshold,
        "sl_percent": config.sl_percent,
        "trailing_sl_trigger": config.trailing_sl_trigger,
        "trailing_sl_trail": config.trailing_sl_trail,
        "daily_loss_cap_percent": config.daily_loss_cap_percent,
        "fund_per_trade_percent": config.fund_per_trade_percent,
        "trading_start_time": config.trading_start_time,
        "trading_end_time": config.trading_end_time,
    }


@router.put("")
async def update_config(update: StrategyConfigUpdate, db=Depends(get_db)):
    """Update strategy config."""
    from backend.models import StrategyConfig

    config = db.query(StrategyConfig).filter(StrategyConfig.is_active == True).first()
    if not config:
        config = StrategyConfig(name="Default", is_active=True)
        db.add(config)

    if update.signal_mode and update.signal_mode not in VALID_SIGNAL_MODES:
        raise HTTPException(400, f"Invalid signal_mode. Must be one of {VALID_SIGNAL_MODES}")

    for field, value in update.model_dump(exclude_none=True).items():
        if field == "sl_percent" and value < 3.0:
            raise HTTPException(400, "Stop loss must be at least 3%")
        setattr(config, field, value)

    db.commit()
    return {"message": "Config updated"}


@router.get("/signal-modes")
async def get_signal_modes():
    """Return available signal modes."""
    return {
        "modes": [
            {"value": "SIMPLE_5MIN", "label": "Simple 5-min", "description": "EMA + RSI + VWAP on 5-min candles"},
            {"value": "ADVANCED_5MIN_1MIN_ADX", "label": "5-min + 1-min + ADX", "description": "5-min trend + ADX filter + 1-min confirmation"},
        ]
    }
