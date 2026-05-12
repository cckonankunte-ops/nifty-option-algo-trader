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
        "client_id_configured": bool(settings.DHAN_CLIENT_ID),
        "token_configured": bool(settings.DHAN_ACCESS_TOKEN),
        "paper_mode": settings.DHAN_SANDBOX_MODE,
        "note": "Use 'Test Connection' button to verify token is valid",
    }


@router.post("/broker/credentials")
async def save_credentials(creds: DhanCredentials):
    """Save Dhan credentials — updates in memory immediately, no restart needed."""
    settings.DHAN_CLIENT_ID = creds.dhan_client_id.strip()
    settings.DHAN_ACCESS_TOKEN = creds.dhan_access_token.strip()

    # Also update .env file so it persists across restarts
    import os
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()

        # Update or add the token lines
        updated_client = False
        updated_token = False
        new_lines = []
        for line in lines:
            if line.startswith("DHAN_CLIENT_ID="):
                new_lines.append(f"DHAN_CLIENT_ID={creds.dhan_client_id}\n")
                updated_client = True
            elif line.startswith("DHAN_ACCESS_TOKEN="):
                new_lines.append(f"DHAN_ACCESS_TOKEN={creds.dhan_access_token}\n")
                updated_token = True
            else:
                new_lines.append(line)

        if not updated_client:
            new_lines.append(f"DHAN_CLIENT_ID={creds.dhan_client_id}\n")
        if not updated_token:
            new_lines.append(f"DHAN_ACCESS_TOKEN={creds.dhan_access_token}\n")

        with open(env_path, "w") as f:
            f.writelines(new_lines)

    except Exception as e:
        return {"message": f"Token updated in memory but failed to save to .env: {e}"}

    return {"message": "Credentials saved. Token active for this session and persisted to .env"}


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
