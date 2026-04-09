"""
Fixed cost_monitor.py
---------------------
Added daily reset via APScheduler so daily_spend doesn't accumulate forever.
Install: pip install apscheduler
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.utils.logger import logger


class CostMonitor:
    def __init__(self, daily_limit_usd: float = 5.0):
        self.daily_limit = daily_limit_usd
        self.daily_spend = 0.0
        self._scheduler: AsyncIOScheduler | None = None

    def start_scheduler(self):
        """Call once at app startup to wire the midnight reset."""
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(self.reset, "cron", hour=0, minute=0, id="cost_reset")
        self._scheduler.start()
        logger.info("CostMonitor: daily reset scheduler started")

    def stop_scheduler(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)

    def track(self, cost_usd: float):
        self.daily_spend += cost_usd
        if self.daily_spend > self.daily_limit * 0.8:
            logger.warning(
                f"Cost alert: ${self.daily_spend:.4f} spent today "
                f"(80%+ of ${self.daily_limit} limit)"
            )
        if self.daily_spend > self.daily_limit:
            raise Exception(
                f"Daily cost limit exceeded: ${self.daily_spend:.4f} > ${self.daily_limit}"
            )

    def reset(self):
        logger.info(f"CostMonitor: daily reset | total spent today=${self.daily_spend:.4f}")
        self.daily_spend = 0.0


cost_monitor = CostMonitor(daily_limit_usd=5.0)