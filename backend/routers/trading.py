"""Trading router — /api/trading endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/trading", tags=["trading"])

# In-memory engine state (will be wired to actual engine in main.py)
_engine_state = {
    "status": "STOPPED",  # RUNNING, STOPPED, DAILY_CAP_HIT
    "fund_amount": 0.0,
    "signal_mode": "SIMPLE_5MIN",
    "last_signal": None,
    "today_pnl": 0.0,
    "today_trades": 0,
    "trading_window": {"start": "09:45", "end": "15:00"},
    "broker": "dhan",
    "paper_mode": True,
    "instrument_master_loaded": False,
    "broker_connected": False,
}


class StartRequest(BaseModel):
    fund_amount: float = Field(..., gt=10000, description="Fund must be > ₹10,000")


class FundRequest(BaseModel):
    fund_amount: float = Field(..., gt=10000, description="Fund must be > ₹10,000")


@router.post("/start")
async def start_engine(request: StartRequest):
    """Start the trading engine."""
    _engine_state["fund_amount"] = request.fund_amount
    _engine_state["status"] = "RUNNING"
    return {"message": "Trading engine started", "fund_amount": request.fund_amount}


@router.post("/stop")
async def stop_engine():
    """Stop the trading engine."""
    _engine_state["status"] = "STOPPED"
    return {"message": "Trading engine stopped"}


@router.get("/status")
async def get_status():
    """Get current engine status."""
    return _engine_state


@router.post("/fund")
async def set_fund(request: FundRequest):
    """Set total trading capital (validate > ₹10,000)."""
    if _engine_state["status"] == "RUNNING":
        raise HTTPException(400, "Cannot change fund while engine is running")
    _engine_state["fund_amount"] = request.fund_amount
    return {"message": "Fund updated", "fund_amount": request.fund_amount}
