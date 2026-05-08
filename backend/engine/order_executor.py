"""Order Executor — places orders via Fyers API or simulates in paper mode."""

import logging
from datetime import datetime
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Handles order placement for live and paper trading modes."""

    def __init__(self, fyers_client=None, db_session=None, get_last_tick=None):
        """
        Args:
            fyers_client: Fyers API client instance (None in paper mode)
            db_session: SQLAlchemy session for logging orders
            get_last_tick: Callable returning last tick price (for paper mode fills)
        """
        self.fyers = fyers_client
        self.db = db_session
        self.get_last_tick = get_last_tick
        self.trading_mode = settings.TRADING_MODE  # "paper" or "live"

    def place_buy_order(
        self, symbol: str, quantity: int, product_type: str = "INTRADAY"
    ) -> dict:
        """
        Place a BUY market order.

        Args:
            symbol: Fyers symbol (e.g., NSE:NIFTY25MAY2224350CE)
            quantity: Number of units to buy
            product_type: INTRADAY (MIS)

        Returns:
            dict with order_id, status, fill_price, message
        """
        if self.trading_mode == "paper":
            return self._simulate_order("BUY", symbol, quantity)

        return self._place_live_order("BUY", symbol, quantity, product_type)

    def place_sell_order(
        self, symbol: str, quantity: int, product_type: str = "INTRADAY"
    ) -> dict:
        """Place a SELL market order to exit position."""
        if self.trading_mode == "paper":
            return self._simulate_order("SELL", symbol, quantity)

        return self._place_live_order("SELL", symbol, quantity, product_type)

    def square_off_all(self, open_positions: list) -> list:
        """
        Close all open positions.

        Args:
            open_positions: List of dicts with symbol, quantity

        Returns:
            List of order results
        """
        results = []
        for pos in open_positions:
            result = self.place_sell_order(pos["symbol"], pos["quantity"])
            results.append(result)
        return results

    @staticmethod
    def format_symbol(strike: int, option_type: str, expiry_date: datetime) -> str:
        """
        Format symbol using Fyers API v3 convention.

        Format: NSE:NIFTY{YY}{MON}{DD}{STRIKE}{CE/PE}
        Example: NSE:NIFTY25MAY2224350CE

        Args:
            strike: ATM strike price (e.g., 24350)
            option_type: "CE" or "PE"
            expiry_date: Expiry datetime

        Returns:
            Formatted symbol string
        """
        yy = expiry_date.strftime("%y")
        mon = expiry_date.strftime("%b").upper()
        dd = expiry_date.strftime("%d")
        return f"NSE:NIFTY{yy}{mon}{dd}{strike}{option_type}"

    def _simulate_order(self, side: str, symbol: str, quantity: int) -> dict:
        """Simulate order in paper trading mode."""
        fill_price = None
        if self.get_last_tick:
            fill_price = self.get_last_tick()

        result = {
            "order_id": f"PAPER_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "status": "FILLED",
            "side": side,
            "symbol": symbol,
            "quantity": quantity,
            "fill_price": fill_price,
            "trading_mode": "paper",
            "message": "Paper trade simulated",
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"[PAPER] {side} {quantity} x {symbol} @ {fill_price}")
        self._log_order(result)
        return result

    def _place_live_order(
        self, side: str, symbol: str, quantity: int, product_type: str
    ) -> dict:
        """Place a live order via Fyers API."""
        try:
            order_data = {
                "symbol": symbol,
                "qty": quantity,
                "type": 2,  # Market order
                "side": 1 if side == "BUY" else -1,
                "productType": product_type,
                "limitPrice": 0,
                "stopPrice": 0,
                "validity": "DAY",
                "disclosedQty": 0,
                "offlineOrder": False,
            }

            response = self.fyers.place_order(data=order_data)

            result = {
                "order_id": response.get("id", "UNKNOWN"),
                "status": "SUBMITTED" if response.get("s") == "ok" else "FAILED",
                "side": side,
                "symbol": symbol,
                "quantity": quantity,
                "fill_price": None,  # Will be updated on fill confirmation
                "trading_mode": "live",
                "message": response.get("message", ""),
                "broker_response": response,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"[LIVE] {side} {quantity} x {symbol} — status: {result['status']}")
            self._log_order(result)
            return result

        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            result = {
                "order_id": None,
                "status": "FAILED",
                "side": side,
                "symbol": symbol,
                "quantity": quantity,
                "fill_price": None,
                "trading_mode": "live",
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
                symbol=order_result.get("symbol", ""),
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
