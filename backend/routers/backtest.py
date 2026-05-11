"""Backtest router — /api/backtest endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from backend.database import get_db
from backend.backtest.backtest_runner import BacktestRunner

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    initial_capital: float = Field(..., gt=0)
    signal_mode: str = Field(default="SIMPLE_5MIN")
    candle_interval: str = Field(default="daily", description="daily, 5, or 1")
    adx_period: int = Field(default=14)
    adx_threshold: int = Field(default=25)
    rsi_upper: int = Field(default=50)
    rsi_lower: int = Field(default=50)


@router.post("/run")
async def run_backtest(request: BacktestRequest):
    """Trigger a backtest with given parameters."""
    runner = BacktestRunner()

    result = runner.run(
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        signal_mode=request.signal_mode,
        candle_interval=request.candle_interval,
        adx_period=request.adx_period,
        adx_threshold=request.adx_threshold,
        rsi_upper=request.rsi_upper,
        rsi_lower=request.rsi_lower,
    )

    return result


@router.get("/results")
async def list_results(db=Depends(get_db)):
    """List all past backtest runs."""
    from backend.models import BacktestResult
    from sqlalchemy import select

    stmt = select(BacktestResult).order_by(BacktestResult.run_date.desc())
    results = db.execute(stmt).scalars().all()
    return [{"id": r.id, "run_date": str(r.run_date), "signal_mode": r.signal_mode,
             "total_return_percent": r.total_return_percent, "total_trades": r.total_trades}
            for r in results]


@router.get("/results/{result_id}")
async def get_result(result_id: int, db=Depends(get_db)):
    """Get full details of one backtest run."""
    from backend.models import BacktestResult

    result = db.get(BacktestResult, result_id)
    if not result:
        raise HTTPException(404, "Backtest result not found")

    return {
        "id": result.id,
        "run_date": str(result.run_date),
        "start_date": result.start_date,
        "end_date": result.end_date,
        "initial_capital": result.initial_capital,
        "final_capital": result.final_capital,
        "signal_mode": result.signal_mode,
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "win_rate": result.win_rate,
        "avg_profit": result.avg_profit,
        "avg_loss": result.avg_loss,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "total_return_percent": result.total_return_percent,
        "adx_filtered_count": result.adx_filtered_count,
        "equity_curve_data": result.equity_curve_data,
        "trade_log": result.trade_log,
    }


@router.get("/debug-candles")
async def debug_candles():
    """Debug endpoint — test if Dhan API returns candle data."""
    from backend.data.dhan_feed import DhanFeed, NIFTY_INDEX_SECURITY_ID
    from backend.config import settings

    feed = DhanFeed(client_id=settings.DHAN_CLIENT_ID, access_token=settings.DHAN_ACCESS_TOKEN)

    from datetime import date, timedelta
    today = date.today().strftime("%Y-%m-%d")
    week_ago = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Try the configured security ID
    df = feed.fetch_nifty_spot_candles_5min(week_ago, today)

    # Also try fetching the instrument list to find Nifty 50
    nifty_info = None
    try:
        sec_list = feed.dhan.fetch_security_list("compact")
        if sec_list and isinstance(sec_list, dict):
            nifty_info = "Security list fetched"
    except Exception as e:
        nifty_info = f"Error: {e}"

    return {
        "dhan_client_initialized": feed.dhan is not None,
        "security_id_used": NIFTY_INDEX_SECURITY_ID,
        "from_date": week_ago,
        "to_date": today,
        "rows_fetched": len(df),
        "columns": list(df.columns) if not df.empty else [],
        "sample_data": df.head(3).to_dict(orient="records") if not df.empty else [],
        "nifty_info": nifty_info,
        "note": "Security ID 13 returns data with prices ~6000-7000. This IS Nifty 50 data - Dhan returns values without the thousands multiplier for INDEX type on NSE_EQ segment.",
    }
