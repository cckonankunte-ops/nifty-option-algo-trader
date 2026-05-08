"""Market Scheduler — APScheduler jobs for trading hours automation.

Trading window: 9:45 AM – 3:00 PM IST (first 30 minutes skipped to avoid open volatility)
Square-off: 3:15 PM IST
"""

import logging
from datetime import datetime, date
from typing import Optional, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

# NSE trading holidays for 2025 (hardcoded)
NSE_HOLIDAYS_2025 = [
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr (Ramadan)
    date(2025, 4, 10),   # Shri Mahavir Jayanti
    date(2025, 4, 14),   # Dr. Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 6, 7),    # Bakri Id
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 16),   # Parsi New Year
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Mahatma Gandhi Jayanti
    date(2025, 10, 21),  # Diwali (Laxmi Pujan)
    date(2025, 10, 22),  # Diwali Balipratipada
    date(2025, 11, 5),   # Guru Nanak Jayanti
    date(2025, 11, 26),  # Constitution Day (tentative)
    date(2025, 12, 25),  # Christmas
]


class MarketScheduler:
    """Manages scheduled trading jobs using APScheduler."""

    def __init__(
        self,
        on_market_open: Optional[Callable] = None,
        on_trading_loop: Optional[Callable] = None,
        on_square_off: Optional[Callable] = None,
        on_market_close: Optional[Callable] = None,
    ):
        """
        Args:
            on_market_open: Callback for 9:15 AM job
            on_trading_loop: Callback for every-minute trading loop
            on_square_off: Callback for 3:15 PM square-off
            on_market_close: Callback for 3:30 PM cleanup
        """
        self.scheduler = AsyncIOScheduler(timezone=IST)
        self._on_market_open = on_market_open
        self._on_trading_loop = on_trading_loop
        self._on_square_off = on_square_off
        self._on_market_close = on_market_close
        self._running = False

    def start(self):
        """Start the scheduler with all trading jobs."""
        # Market open job — 9:15 AM Mon-Fri
        self.scheduler.add_job(
            self._market_open_job,
            CronTrigger(hour=9, minute=15, day_of_week="mon-fri", timezone=IST),
            id="market_open",
            replace_existing=True,
        )

        # Trading loop — every 1 minute, 9:45 AM to 3:00 PM Mon-Fri
        # First 30 minutes skipped to avoid open volatility
        self.scheduler.add_job(
            self._trading_loop_job,
            CronTrigger(
                hour="9-14",
                minute="*/1",
                day_of_week="mon-fri",
                timezone=IST,
            ),
            id="trading_loop",
            replace_existing=True,
        )

        # Square-off job — 3:15 PM Mon-Fri
        self.scheduler.add_job(
            self._square_off_job,
            CronTrigger(hour=15, minute=15, day_of_week="mon-fri", timezone=IST),
            id="square_off",
            replace_existing=True,
        )

        # Market close job — 3:30 PM Mon-Fri
        self.scheduler.add_job(
            self._market_close_job,
            CronTrigger(hour=15, minute=30, day_of_week="mon-fri", timezone=IST),
            id="market_close",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True
        logger.info("Market scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Market scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def _is_holiday(self, check_date: Optional[date] = None) -> bool:
        """Check if given date is an NSE trading holiday."""
        if check_date is None:
            check_date = datetime.now(IST).date()
        return check_date in NSE_HOLIDAYS_2025

    def _is_within_trading_window(self) -> bool:
        """Check if current time is within 9:45 AM – 3:00 PM IST."""
        now = datetime.now(IST)
        start_hour, start_min = 9, 45
        end_hour, end_min = 15, 0

        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min

        return start_minutes <= current_minutes <= end_minutes

    async def _market_open_job(self):
        """9:15 AM — load instrument master, verify broker, reset daily counters."""
        if self._is_holiday():
            logger.info("Today is an NSE holiday — skipping all trading jobs")
            return

        logger.info("Market open job triggered")

        # Dhan does not need daily token refresh — token lasts 30 days.
        # Instead, load instrument master and verify connection.
        if self._on_market_open:
            await self._on_market_open()

    async def _trading_loop_job(self):
        """Every 1 minute — run signal + risk cycle (9:45 AM – 3:00 PM only)."""
        if self._is_holiday():
            return

        if not self._is_within_trading_window():
            return

        logger.debug("Trading loop tick")
        if self._on_trading_loop:
            await self._on_trading_loop()

    async def _square_off_job(self):
        """3:15 PM — close all open positions."""
        if self._is_holiday():
            return

        logger.info("Square-off job triggered")
        if self._on_square_off:
            await self._on_square_off()

    async def _market_close_job(self):
        """3:30 PM — stop feed, generate daily summary."""
        if self._is_holiday():
            return

        logger.info("Market close job triggered")
        if self._on_market_close:
            await self._on_market_close()
