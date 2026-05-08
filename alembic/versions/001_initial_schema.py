"""Initial schema with all tables.

Revision ID: 001
Revises: None
Create Date: 2025-05-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_configs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(100), nullable=False, server_default="Default"),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("signal_mode", sa.String(50), server_default="SIMPLE_5MIN"),
        sa.Column("ema_fast", sa.Integer(), server_default="9"),
        sa.Column("ema_slow", sa.Integer(), server_default="21"),
        sa.Column("rsi_period", sa.Integer(), server_default="14"),
        sa.Column("rsi_upper", sa.Integer(), server_default="60"),
        sa.Column("rsi_lower", sa.Integer(), server_default="40"),
        sa.Column("adx_period", sa.Integer(), server_default="14"),
        sa.Column("adx_threshold", sa.Integer(), server_default="25"),
        sa.Column("sl_percent", sa.Float(), server_default="3.0"),
        sa.Column("trailing_sl_trigger", sa.Float(), server_default="4.0"),
        sa.Column("trailing_sl_trail", sa.Float(), server_default="2.0"),
        sa.Column("daily_loss_cap_percent", sa.Float(), server_default="6.0"),
        sa.Column("fund_per_trade_percent", sa.Float(), server_default="25.0"),
        sa.Column("trading_start_time", sa.String(10), server_default="09:45"),
        sa.Column("trading_end_time", sa.String(10), server_default="15:00"),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("strike", sa.Integer(), nullable=False),
        sa.Column("option_type", sa.String(2), nullable=False),
        sa.Column("entry_time", sa.DateTime(), nullable=False),
        sa.Column("exit_time", sa.DateTime(), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("signal_used", sa.JSON(), nullable=True),
        sa.Column("sl_price", sa.Float(), nullable=True),
        sa.Column("peak_price", sa.Float(), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("pnl_percent", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="OPEN"),
        sa.Column("exit_reason", sa.String(30), nullable=True),
        sa.Column("trigger_type", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("run_name", sa.String(100), nullable=True),
        sa.Column("run_date", sa.DateTime()),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
        sa.Column("initial_capital", sa.Float(), nullable=False),
        sa.Column("final_capital", sa.Float(), nullable=True),
        sa.Column("signal_mode", sa.String(50), nullable=True),
        sa.Column("total_trades", sa.Integer(), server_default="0"),
        sa.Column("winning_trades", sa.Integer(), server_default="0"),
        sa.Column("losing_trades", sa.Integer(), server_default="0"),
        sa.Column("win_rate", sa.Float(), server_default="0.0"),
        sa.Column("avg_profit", sa.Float(), server_default="0.0"),
        sa.Column("avg_loss", sa.Float(), server_default="0.0"),
        sa.Column("max_drawdown", sa.Float(), server_default="0.0"),
        sa.Column("sharpe_ratio", sa.Float(), server_default="0.0"),
        sa.Column("total_return_percent", sa.Float(), server_default="0.0"),
        sa.Column("adx_filtered_count", sa.Integer(), server_default="0"),
        sa.Column("equity_curve_data", sa.JSON(), nullable=True),
        sa.Column("trade_log", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
    )

    op.create_table(
        "order_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("trade_id", sa.Integer(), nullable=True),
        sa.Column("order_type", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("broker_response", sa.JSON(), nullable=True),
        sa.Column("trading_mode", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "daily_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("date", sa.String(10), nullable=False, unique=True),
        sa.Column("total_trades", sa.Integer(), server_default="0"),
        sa.Column("winning_trades", sa.Integer(), server_default="0"),
        sa.Column("losing_trades", sa.Integer(), server_default="0"),
        sa.Column("total_pnl", sa.Float(), server_default="0.0"),
        sa.Column("total_pnl_percent", sa.Float(), server_default="0.0"),
        sa.Column("daily_cap_hit", sa.Boolean(), server_default="0"),
        sa.Column("signal_mode_used", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("daily_summaries")
    op.drop_table("order_logs")
    op.drop_table("backtest_results")
    op.drop_table("trades")
    op.drop_table("strategy_configs")
