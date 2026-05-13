"""History router — /api/history endpoints."""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from backend.database import get_db

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/trades")
async def get_trades(
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    status: Optional[str] = Query(None),
    option_type: Optional[str] = Query(None, description="CE or PE"),
    trigger_type: Optional[str] = Query(None, description="paper or live"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db=Depends(get_db),
):
    """Paginated trade history with filters."""
    from backend.models import Trade
    from sqlalchemy import select

    stmt = select(Trade).order_by(Trade.created_at.desc())

    if status:
        stmt = stmt.where(Trade.status == status)
    if option_type:
        stmt = stmt.where(Trade.option_type == option_type)
    if trigger_type:
        stmt = stmt.where(Trade.trigger_type == trigger_type)

    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    trades = db.execute(stmt).scalars().all()

    return {
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "strike": t.strike,
                "option_type": t.option_type,
                "entry_time": str(t.entry_time),
                "exit_time": str(t.exit_time) if t.exit_time else None,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent,
                "status": t.status,
                "exit_reason": t.exit_reason,
                "trigger_type": t.trigger_type,
            }
            for t in trades
        ],
        "page": page,
        "page_size": page_size,
    }


@router.get("/daily-summary")
async def get_daily_summary(db=Depends(get_db)):
    """Daily P&L summaries."""
    from backend.models import DailySummary
    from sqlalchemy import select

    stmt = select(DailySummary).order_by(DailySummary.date.desc()).limit(30)
    summaries = db.execute(stmt).scalars().all()

    return [
        {
            "date": s.date,
            "total_trades": s.total_trades,
            "winning_trades": s.winning_trades,
            "losing_trades": s.losing_trades,
            "total_pnl": s.total_pnl,
            "daily_cap_hit": s.daily_cap_hit,
        }
        for s in summaries
    ]
