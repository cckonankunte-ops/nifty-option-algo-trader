"""Order Executor — places orders via DhanHQ API or simulates in paper mode."""

import logging
from datetime import datetime, date
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Handles order placement for live and paper trading via Dhan."""

    def __init__(self, dhan_feed=None, db_session=None):
        """
        Args:
            dhan_feed: DhanFeed instance for security_id lookups and last price
            db_session: SQLAlchemy session for logging orders
        """
        self.dhan_feed = dhan_feed
        self.db = db_session
        self.paper_mode = settings.DHAN_SANDBOX_MODE

        # Initialize Dhan client for order placement
        self.dhan = None
        if not self.paper_mode:
            try:
                from dhanhq import dhanhq as DhanHQ
                self.dhan = DhanHQ({"access_token": settings.DHAN_ACCESS_TOKEN, "client_id": settings.DHAN_CLIENT_ID})
            except TypeError:
                try:
                    from dhanhq import dhanhq as DhanHQ
                    self.dhan = DhanHQ(settings.DHAN_CLIENT_ID, settings.DHAN_ACCESS_TOKEN)
                except Exception as e:
                    logger.error(f"Failed to initialize Dhan order client (fallback): {e}")
            except Exception as e:
                logger.error(f"Failed to initialize Dhan order client: {e}")

    def place_buy_order(
        self,
        strike: float,
        expiry_date: date,
        option_type: str,
        quantity: int,
        signal_info: Optional[dict] = None,
    ) -> dict:
        """
        Place a BUY market order for Nifty options.

        Args:
            strike: ATM strike price
            expiry_date: Weekly expiry date
            option_type: "CE" or "PE"
            quantity: Must be multiple of 25
            signal_info: Full signal dict for logging
        """
        if self.paper_mode:
            return self._simulate_buy(strike, expiry_date, option_type, quantity, signal_info)

        # Resolve security_id
        try:
            security_id = self.dhan_feed.get_security_id(strike, expiry_date, option_type)
        except ValueError as e:
            logger.error(f"Cannot place order: {e}")
            return {"status": "FAILED", "message": str(e)}

        return self._place_live_buy(security_id, quantity, strike, option_type, expiry_date, signal_info)

    def place_sell_order(
        self,
        security_id: str,
        quantity: int,
        reason: str = "SQUARE_OFF",
    ) -> dict:
        """
        Place a SELL market order to exit position.

        Args:
            security_id: Dhan security ID of the option
            quantity: Number of units to sell
            reason: SL_HIT | TRAILING_SL | SQUARE_OFF | DAILY_CAP
        """
        if self.paper_mode:
            return self._simulate_sell(security_id, quantity, reason)

        return self._place_live_sell(security_id, quantity, reason)

    def square_off_all(self, open_positions: list) -> list:
        """
        Close all open positions.

        Args:
            open_positions: List of dicts with security_id, quantity
        """
        results = []
        for pos in open_positions:
            result = self.place_sell_order(pos["security_id"], pos["quantity"], "SQUARE_OFF")
            results.append(result)
        return results

    def verify_connection(self) -> bool:
        """Verify Dhan API connectivity by calling get_fund_limits."""
        if self.paper_mode:
            return True  # Paper mode always "connected"

        try:
            if self.dhan is None:
                from dhanhq import dhanhq
                self.dhan = dhanhq(settings.DHAN_CLIENT_ID, settings.DHAN_ACCESS_TOKEN)

            response = self.dhan.get_fund_limits()
            if response and response.get("status") == "success":
                logger.info("Dhan broker connection verified")
                return True
            else:
                logger.error(f"Dhan connection check failed: {response}")
                return False
        except Exception as e:
            logger.error(f"Dhan connection verification failed: {e}")
            return False

    @staticmethod
    def format_symbol(strike: int, option_type: str, expiry_date: datetime) -> str:
        """
        Format display symbol (for logging/UI only — Dhan uses security_id for orders).

        Format: NIFTY {DD} {MON} {STRIKE} {CE/PE}
        """
        mon = expiry_date.strftime("%b").upper()
        dd = expiry_date.strftime("%d")
        return f"NIFTY {dd} {mon} {strike} {option_type}"

    # ─── Private Methods ─────────────────────────────────────────────

    def _simulate_buy(self, strike, expiry_date, option_type, quantity, signal_info) -> dict:
        """Simulate buy order in paper mode."""
        # Get last price for fill simulation
        fill_price = None
        if self.dhan_feed:
            try:
                sid = self.dhan_feed.get_security_id(strike, expiry_date, option_type)
                fill_price = self.dhan_feed.get_last_price(sid)
            except (ValueError, Exception):
                fill_price = None

        result = {
            "order_id": f"PAPER_BUY_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "status": "PAPER_FILLED",
            "side": "BUY",
            "security_id": None,
            "strike": strike,
            "option_type": option_type,
            "quantity": quantity,
            "fill_price": fill_price,
            "trading_mode": "paper",
            "message": "Paper trade simulated",
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"[PAPER] BUY {quantity} x NIFTY {int(strike)}{option_type} @ {fill_price}")
        self._log_order(result)
        return result

    def _simulate_sell(self, security_id, quantity, reason) -> dict:
        """Simulate sell order in paper mode."""
        fill_price = None
        if self.dhan_feed:
            fill_price = self.dhan_feed.get_last_price(security_id)

        result = {
            "order_id": f"PAPER_SELL_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "status": "PAPER_FILLED",
            "side": "SELL",
            "security_id": security_id,
            "quantity": quantity,
            "fill_price": fill_price,
            "trading_mode": "paper",
            "reason": reason,
            "message": "Paper exit simulated",
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"[PAPER] SELL {quantity} x {security_id} @ {fill_price} reason={reason}")
        self._log_order(result)
        return result

    def _place_live_buy(self, security_id, quantity, strike, option_type, expiry_date, signal_info) -> dict:
        """Place live buy order via Dhan API."""
        try:
            from dhanhq import dhanhq as dhan_constants

            response = self.dhan.place_order(
                security_id=security_id,
                exchange_segment=self.dhan.NSE_FNO,
                transaction_type=self.dhan.BUY,
                quantity=quantity,
                order_type=self.dhan.MARKET,
                product_type=self.dhan.INTRADAY,
                price=0,
                trigger_price=0,
            )

            status = "SUBMITTED" if response.get("status") == "success" else "FAILED"

            result = {
                "order_id": response.get("data", {}).get("orderId", "UNKNOWN"),
                "status": status,
                "side": "BUY",
                "security_id": security_id,
                "strike": strike,
                "option_type": option_type,
                "quantity": quantity,
                "fill_price": None,
                "trading_mode": "live",
                "message": response.get("remarks", ""),
                "broker_response": response,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"[LIVE] BUY {quantity} x {security_id} — status: {status}")
            self._log_order(result)
            return result

        except Exception as e:
            logger.error(f"Live buy order failed: {e}")
            result = {
                "order_id": None,
                "status": "FAILED",
                "side": "BUY",
                "security_id": security_id,
                "quantity": quantity,
                "fill_price": None,
                "trading_mode": "live",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            self._log_order(result)
            return result

    def _place_live_sell(self, security_id, quantity, reason) -> dict:
        """Place live sell order via Dhan API."""
        try:
            response = self.dhan.place_order(
                security_id=security_id,
                exchange_segment=self.dhan.NSE_FNO,
                transaction_type=self.dhan.SELL,
                quantity=quantity,
                order_type=self.dhan.MARKET,
                product_type=self.dhan.INTRADAY,
                price=0,
                trigger_price=0,
            )

            status = "SUBMITTED" if response.get("status") == "success" else "FAILED"

            result = {
                "order_id": response.get("data", {}).get("orderId", "UNKNOWN"),
                "status": status,
                "side": "SELL",
                "security_id": security_id,
                "quantity": quantity,
                "fill_price": None,
                "trading_mode": "live",
                "reason": reason,
                "message": response.get("remarks", ""),
                "broker_response": response,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"[LIVE] SELL {quantity} x {security_id} reason={reason} — status: {status}")
            self._log_order(result)
            return result

        except Exception as e:
            logger.error(f"Live sell order failed: {e}")
            result = {
                "order_id": None,
                "status": "FAILED",
                "side": "SELL",
                "security_id": security_id,
                "quantity": quantity,
                "fill_price": None,
                "trading_mode": "live",
                "reason": reason,
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            self._log_order(result)
            return result

    def _log_order(self, order_result: dict):
        """Log order to database."""
        if self.db is None:
            return

        try:
            from backend.models import OrderLog

            log = OrderLog(
                trade_id=None,
                order_type=order_result.get("side", "UNKNOWN"),
                symbol=order_result.get("security_id", ""),
                quantity=order_result.get("quantity", 0),
                price=order_result.get("fill_price"),
                status=order_result.get("status", "UNKNOWN"),
                broker_response=order_result.get("broker_response"),
                trading_mode=order_result.get("trading_mode", "paper"),
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log order: {e}")
