"""Settings router — /api/settings endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from backend.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    log_level: Optional[str] = None


class DhanCredentials(BaseModel):
    dhan_client_id: str
    dhan_access_token: str


@router.get("")
async def get_settings():
    """Get current application settings."""
    return {
        "broker": "dhan",
        "broker_connected": bool(settings.DHAN_ACCESS_TOKEN),
        "paper_mode": settings.DHAN_SANDBOX_MODE,
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
        "broker": "dhan",
        "connected": bool(settings.DHAN_ACCESS_TOKEN),
        "client_id_configured": bool(settings.DHAN_CLIENT_ID),
        "paper_mode": settings.DHAN_SANDBOX_MODE,
    }


@router.post("/broker/credentials")
async def save_credentials(creds: DhanCredentials):
    """Save Dhan credentials (runtime only — persist in .env manually)."""
    settings.DHAN_CLIENT_ID = creds.dhan_client_id
    settings.DHAN_ACCESS_TOKEN = creds.dhan_access_token
    return {"message": "Credentials updated for this session"}


@router.post("/broker/verify")
async def verify_broker():
    """Verify Dhan API connectivity."""
    from backend.engine.order_executor import OrderExecutor

    executor = OrderExecutor()
    connected = executor.verify_connection()
    return {
        "connected": connected,
        "message": "Dhan connection verified" if connected else "Connection failed — check credentials",
    }
