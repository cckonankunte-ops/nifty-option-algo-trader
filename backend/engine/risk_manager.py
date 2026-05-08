"""Risk Manager — enforces stop loss, trailing SL, daily loss cap, position sizing."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Nifty options lot size
NIFTY_LOT_SIZE = 25


class RiskManager:
    """Manages risk controls for the trading engine."""

    def __init__(self, config, total_fund: float):
        """
        Args:
            config: StrategyConfig with sl_percent, trailing_sl_trigger,
                    trailing_sl_trail, daily_loss_cap_percent, fund_per_trade_percent
            total_fund: Total trading capital in INR
        """
        self.config = config
        self.total_fund = total_fund

        # Risk parameters
        self.sl_percent = max(getattr(config, "sl_percent", 3.0), 3.0)  # min 3%
        self.trailing_trigger = getattr(config, "trailing_sl_trigger", 4.0)
        self.trailing_trail = getattr(config, "trailing_sl_trail", 2.0)
        self.daily_cap_percent = getattr(config, "daily_loss_cap_percent", 6.0)
        self.fund_per_trade_pct = getattr(config, "fund_per_trade_percent", 25.0)

        # State
        self.has_open_position = False
        self.daily_realized_loss = 0.0
        self.daily_cap_hit = False

        # Trailing SL state
        self._entry_price: Optional[float] = None
        self._sl_price: Optional[float] = None
        self._peak_price: Optional[float] = None
        self._trailing_active = False

    def can_trade(self) -> bool:
        """Check if a new trade is allowed."""
        if self.has_open_position:
            return False
        if self.daily_cap_hit:
            return False
        return True

    def calculate_quantity(self, option_price: float) -> int:
        """
        Calculate trade quantity based on fund allocation.

        Returns quantity in multiples of NIFTY_LOT_SIZE (25).
        Returns 0 if insufficient funds for even 1 lot.
        """
        allocated_fund = self.total_fund * (self.fund_per_trade_pct / 100.0)
        cost_per_lot = NIFTY_LOT_SIZE * option_price

        if cost_per_lot > allocated_fund:
            logger.warning("Insufficient fund for minimum lot size")
            return 0

        lots = int(allocated_fund / cost_per_lot)
        if lots < 1:
            logger.warning("Insufficient fund for minimum lot size")
            return 0

        return lots * NIFTY_LOT_SIZE

    def set_stop_loss(self, entry_price: float) -> float:
        """
        Set initial stop loss for a new position.

        Returns the SL price level.
        """
        self._entry_price = entry_price
        self._peak_price = entry_price
        self._trailing_active = False
        self._sl_price = entry_price * (1 - self.sl_percent / 100.0)
        self.has_open_position = True
        return self._sl_price

    def on_tick(self, current_price: float) -> dict:
        """
        Evaluate risk on every tick while position is open.

        Returns:
            dict with keys:
                action: "HOLD" | "EXIT_SL" | "EXIT_TRAILING_SL"
                sl_price: current stop loss level
                peak_price: highest price since entry
                trailing_active: whether trailing SL is active
        """
        if not self.has_open_position or self._entry_price is None:
            return {"action": "HOLD", "sl_price": None, "peak_price": None, "trailing_active": False}

        # Update peak price
        if current_price > self._peak_price:
            self._peak_price = current_price

        # Check trailing SL activation
        profit_pct = ((self._peak_price - self._entry_price) / self._entry_price) * 100
        if not self._trailing_active and profit_pct >= self.trailing_trigger:
            self._trailing_active = True

        # Update trailing SL level
        if self._trailing_active:
            trailing_sl = self._peak_price * (1 - self.trailing_trail / 100.0)
            if trailing_sl > self._sl_price:
                self._sl_price = trailing_sl

        # Check if SL hit
        if current_price <= self._sl_price:
            action = "EXIT_TRAILING_SL" if self._trailing_active else "EXIT_SL"
            return {
                "action": action,
                "sl_price": self._sl_price,
                "peak_price": self._peak_price,
                "trailing_active": self._trailing_active,
            }

        return {
            "action": "HOLD",
            "sl_price": self._sl_price,
            "peak_price": self._peak_price,
            "trailing_active": self._trailing_active,
        }

    def record_trade_exit(self, pnl: float):
        """Record a trade exit and update daily P&L."""
        self.has_open_position = False
        self._entry_price = None
        self._sl_price = None
        self._peak_price = None
        self._trailing_active = False

        if pnl < 0:
            self.daily_realized_loss += abs(pnl)

        # Check daily cap
        if self.check_daily_cap():
            self.daily_cap_hit = True

    def check_daily_cap(self) -> bool:
        """Check if daily loss cap has been hit."""
        cap_amount = self.total_fund * (self.daily_cap_percent / 100.0)
        return self.daily_realized_loss >= cap_amount

    def reset_daily(self):
        """Reset daily counters at start of new trading day."""
        self.daily_realized_loss = 0.0
        self.daily_cap_hit = False

    @property
    def current_sl_price(self) -> Optional[float]:
        """Get current stop loss price."""
        return self._sl_price

    @property
    def current_peak_price(self) -> Optional[float]:
        """Get current peak price."""
        return self._peak_price
