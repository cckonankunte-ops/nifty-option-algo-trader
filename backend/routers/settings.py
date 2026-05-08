"""Settings router — /api/settings endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from backend.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    log_level: Optional[str] = None


@router.get("")
async def get_settings():
    """Get current application settings."""
    return {
        "broker_connected": bool(settings.FYERS_ACCESS_TOKEN),
        "trading_mode": settings.TRADING_MODE,
        "environment": settings.ENVIRONMENT,
        "log_level": settings.LOG_LEVEL,
        "trading_window": {"start": "09:45", "end": "15:00"},
    }


@router.put("")
async def update_settings(update: SettingsUpdate):
    """Update settings without server restart."""
    if update.log_level:
        settings.LOG_LEVEL = update.log_level
    return {"message": "Settings updated"}


@router.get("/broker/status")
async def broker_status():
    """Check broker connection status."""
    return {
        "connected": bool(settings.FYERS_ACCESS_TOKEN),
        "app_id_configured": bool(settings.FYERS_APP_ID),
        "trading_mode": settings.TRADING_MODE,
    }
