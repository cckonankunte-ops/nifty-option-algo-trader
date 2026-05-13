"""Trading Engine — orchestrates signal generation, risk management, and order execution."""

import logging
import asyncio
import time
import threading
from datetime import datetime, date
from typing import Optional

import pandas as pd
import pytz

from backend.config import settings
from backend.engine.signal_engine import SignalEngine
from backend.engine.risk_manager import RiskManager
from backend.engine.order_executor import OrderExecutor
from backend.data.dhan_feed import DhanFeed
from backend.data.candle_builder import CandleBuilder
from backend.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

LOT_SIZE = 65


def _broadcast(event_type: str, payload: dict):
    """Safely broadcast WebSocket event from background thread."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ws_manager.broadcast(event_type, payload))
        loop.close()
    except Exception:
        pass  # Non-critical — UI update only


class TradingEngine:
    """Main trading engine that runs the signal-risk-order loop."""

    def __init__(self):
        self.running = False
        self.config = {}
        self.fund_amount = 0.0
        self.capital = 0.0
        self.daily_pnl = 0.0
        self.today_trades = 0
        self.position = None
        self.today_trade_log = []  # Store today's completed trades
        self._loop_thread: Optional[threading.Thread] = None

        # Components
        self.dhan_feed: Optional[DhanFeed] = None
        self.signal_engine: Optional[SignalEngine] = None
        self.risk_manager: Optional[RiskManager] = None
        self.order_executor: Optional[OrderExecutor] = None

    def start(self, fund_amount: float, config: dict):
        """Start the trading engine with given settings."""
        if self.running:
            return {"error": "Engine already running"}

        self.fund_amount = fund_amount
        self.capital = fund_amount
        self.config = config
        self.daily_pnl = 0.0
        self.today_trades = 0
        self.position = None

        # Initialize components
        try:
            # Dhan Feed
            self.dhan_feed = DhanFeed(
                client_id=settings.DHAN_CLIENT_ID,
                access_token=settings.DHAN_ACCESS_TOKEN,
            )

            # Load instrument master
            if not self.dhan_feed.load_instrument_master():
                logger.error("Failed to load instrument master")
                return {"error": "Failed to load instrument master"}

            # Signal Engine config mock
            from unittest.mock import MagicMock
            sig_config = MagicMock()
            sig_config.signal_mode = config.get("signal_mode", "SIMPLE_5MIN")
            sig_config.ema_fast = 9
            sig_config.ema_slow = 21
            sig_config.rsi_period = 14
            sig_config.rsi_upper = config.get("rsi_upper", 55)
            sig_config.rsi_lower = config.get("rsi_lower", 45)
            sig_config.adx_period = 14
            sig_config.adx_threshold = 25
            sig_config.sl_percent = config.get("sl_percent", 20)
            sig_config.trailing_sl_trigger = 4.0
            sig_config.trailing_sl_trail = 2.0
            sig_config.daily_loss_cap_percent = 6.0
            sig_config.fund_per_trade_percent = 10.0
            self.signal_engine = SignalEngine(sig_config)

            # Risk Manager
            self.risk_manager = RiskManager(sig_config, fund_amount)

            # Order Executor
            self.order_executor = OrderExecutor(dhan_feed=self.dhan_feed)

            self.running = True

            # Start the trading loop in a background thread
            self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
            self._loop_thread.start()

            logger.info(f"Trading engine started: mode={config.get('trading_mode', 'paper')}, fund={fund_amount}")
            _broadcast("ENGINE_STATUS", {"status": "running", "mode": config.get("trading_mode", "paper")})
            return {"status": "started"}

        except Exception as e:
            logger.error(f"Failed to start trading engine: {e}")
            return {"error": str(e)}

    def stop(self):
        """Stop the trading engine."""
        self.running = False
        # Square off any open position
        if self.position:
            self._square_off()
        logger.info("Trading engine stopped")
        return {"status": "stopped"}

    def get_status(self) -> dict:
        """Get current engine status."""
        return {
            "status": "RUNNING" if self.running else "STOPPED",
            "fund_amount": self.fund_amount,
            "capital": round(self.capital, 2),
            "today_pnl": round(self.daily_pnl, 2),
            "today_trades": self.today_trades,
            "position": self.position,
            "today_trade_log": self.today_trade_log,
            "paper_mode": self.config.get("trading_mode", "paper") == "paper",
            "signal_mode": self.config.get("signal_mode", "SIMPLE_5MIN"),
            "trading_window": {"start": "09:45", "end": "15:15"},
            "broker": "dhan",
            "instrument_master_loaded": self.dhan_feed.is_master_loaded if self.dhan_feed else False,
            "broker_connected": True,
        }

    def _run_loop(self):
        """Main trading loop — runs every 60 seconds during market hours."""
        logger.info("Trading loop started")

        while self.running:
            try:
                now = datetime.now(IST)
                total_min = now.hour * 60 + now.minute

                # Only trade between 9:45 AM and 3:00 PM IST
                if total_min < 585 or total_min > 900:
                    # Square off at 3:15 PM
                    if total_min >= 915 and self.position:
                        self._square_off()
                    time.sleep(60)
                    continue

                # Skip weekends
                if now.weekday() >= 5:
                    time.sleep(60)
                    continue

                # Run signal check
                self._check_and_trade()

            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                try:
                    _broadcast("ERROR", {"message": str(e)})
                except Exception:
                    pass

            # Wait 60 seconds before next check
            time.sleep(60)

        logger.info("Trading loop ended")

    def _check_and_trade(self):
        """Fetch candles, generate signal, execute if conditions met."""
        interval = self.config.get("candle_interval", "5")

        # Fetch recent candles from Dhan
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        yesterday_str = (datetime.now(IST) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            candles = self.dhan_feed._fetch_intraday_range(
                security_id="61093",  # Current Nifty futures
                exchange_segment="NSE_FNO",
                instrument_type="FUTIDX",
                interval=interval,
                from_date=yesterday_str,
                to_date=today_str,
            )
        except Exception as e:
            logger.error(f"Failed to fetch candles: {e}")
            return

        if candles.empty or len(candles) < 25:
            logger.debug("Not enough candles yet")
            return

        # Generate signal
        result = self.signal_engine.generate_signal(candles_5min=candles)
        signal = result["signal"]

        # Broadcast signal event
        _broadcast("SIGNAL", result)

        # Check daily loss cap
        lot_sizing = self.config.get("lot_sizing", "fixed")
        daily_cap = self.capital * 0.06 if lot_sizing == "compounding" else self.fund_amount * 0.06
        if self.daily_pnl <= -daily_cap:
            if self.position:
                self._square_off()
            return

        # If position open, check SL
        if self.position:
            current_price = candles.iloc[-1]["close"]
            self._check_exit(current_price)
            return

        # No position — check for entry
        if signal in ("BUY_CALL", "BUY_PUT"):
            self._enter_trade(signal, candles)

    def _enter_trade(self, signal: str, candles: pd.DataFrame):
        """Enter a new trade."""
        current_price = candles.iloc[-1]["close"]
        option_type = "CALL" if signal == "BUY_CALL" else "PUT"
        sl_pct = self.config.get("sl_percent", 20)

        # Calculate ITM strike with premium >= 100
        if option_type == "CALL":
            strike = int((current_price // 100) * 100)
            while True:
                intrinsic = current_price - strike
                premium = intrinsic + 40
                if premium >= 100:
                    break
                strike -= 100
        else:
            strike = int(((current_price // 100) + 1) * 100)
            while True:
                intrinsic = strike - current_price
                premium = intrinsic + 40
                if premium >= 100:
                    break
                strike += 100

        # Calculate quantity
        lot_sizing = self.config.get("lot_sizing", "fixed")
        fund_per_trade = self.fund_amount * 0.10 if lot_sizing == "fixed" else self.capital * 0.10
        lots = max(1, int(fund_per_trade / (premium * LOT_SIZE)))
        quantity = lots * LOT_SIZE

        # Get expiry
        expiry = SignalEngine.get_weekly_expiry(datetime.now(IST))

        # Place order
        order_result = self.order_executor.place_buy_order(
            strike=float(strike),
            expiry_date=expiry.date(),
            option_type=option_type,
            quantity=quantity,
            signal_info={"signal": signal, "spot": current_price},
        )

        if order_result.get("status") in ("PAPER_FILLED", "SUBMITTED"):
            fill_price = order_result.get("fill_price") or premium
            self.position = {
                "entry_price": fill_price,
                "spot_at_entry": current_price,
                "strike": strike,
                "option_type": option_type,
                "quantity": quantity,
                "sl_price": fill_price * (1 - sl_pct / 100),
                "peak_price": fill_price,
                "entry_time": datetime.now(IST).strftime("%Y-%m-%d %H:%M"),
                "signal": signal,
                "security_id": order_result.get("security_id"),
            }
            self.today_trades += 1
            logger.info(f"Entered: {signal} strike={strike} qty={quantity} premium={fill_price:.1f}")

            _broadcast("ORDER_PLACED", {
                    "signal": signal, "strike": strike, "quantity": quantity, "premium": fill_price
                })

    def _check_exit(self, current_price: float):
        """Check if position should be exited (SL or trailing SL)."""
        if not self.position:
            return

        # Simulate option price
        spot_change = current_price - self.position["spot_at_entry"]
        delta = 0.65
        if self.position["option_type"] == "CALL":
            current_opt_price = self.position["entry_price"] + (spot_change * delta)
        else:
            current_opt_price = self.position["entry_price"] - (spot_change * delta)
        current_opt_price = max(current_opt_price, 1)

        # Update peak
        if current_opt_price > self.position["peak_price"]:
            self.position["peak_price"] = current_opt_price

        # Check SL
        if current_opt_price <= self.position["sl_price"]:
            self._exit_trade(self.position["sl_price"], "SL_HIT")

    def _square_off(self):
        """Square off open position."""
        if not self.position:
            return
        # Use SL price as worst case for square-off
        exit_price = self.position.get("peak_price", self.position["entry_price"])
        self._exit_trade(exit_price, "SQUARE_OFF")

    def _exit_trade(self, exit_price: float, reason: str):
        """Exit the current position."""
        if not self.position:
            return

        pnl = (exit_price - self.position["entry_price"]) * self.position["quantity"]
        self.capital += pnl
        self.daily_pnl += pnl

        # Log completed trade
        completed_trade = {
            "entry_time": self.position.get("entry_time", ""),
            "exit_time": datetime.now(IST).strftime("%Y-%m-%d %H:%M"),
            "signal": self.position.get("signal", ""),
            "option_type": self.position.get("option_type", ""),
            "strike": self.position.get("strike", 0),
            "quantity": self.position.get("quantity", 0),
            "entry_price": round(self.position.get("entry_price", 0), 2),
            "exit_price": round(exit_price, 2),
            "pnl": round(pnl, 2),
            "exit_reason": reason,
        }
        self.today_trade_log.append(completed_trade)

        logger.info(f"Exited: {reason} pnl={pnl:.0f} exit_price={exit_price:.1f}")

        # Place sell order
        security_id = self.position.get("security_id", "")
        if security_id:
            self.order_executor.place_sell_order(
                security_id=security_id,
                quantity=self.position["quantity"],
                reason=reason,
            )

        try:
            _broadcast("SL_HIT" if "SL" in reason else "ORDER_FILLED", {
                "reason": reason, "pnl": round(pnl, 2), "exit_price": round(exit_price, 2)
            })
        except Exception:
            pass

        self.position = None


# Singleton instance
trading_engine = TradingEngine()
