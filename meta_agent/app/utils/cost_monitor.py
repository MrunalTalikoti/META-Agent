from app.utils.logger import logger

class CostMonitor:
    """Simple cost tracking and alerting"""
    
    def __init__(self, daily_limit_usd: float = 5.0):
        self.daily_limit = daily_limit_usd
        self.daily_spend = 0.0
    
    def track(self, cost_usd: float):
        self.daily_spend += cost_usd
        
        if self.daily_spend > self.daily_limit * 0.8:
            logger.warning(
                f"Cost alert: ${self.daily_spend:.2f} spent today "
                f"(80% of ${self.daily_limit} limit)"
            )
        
        if self.daily_spend > self.daily_limit:
            raise Exception(
                f"Daily cost limit exceeded: ${self.daily_spend:.2f} > ${self.daily_limit}"
            )
    
    def reset(self):
        """Call this daily (use a cron job or task scheduler)"""
        logger.info(f"Daily spend: ${self.daily_spend:.4f}")
        self.daily_spend = 0.0

# Global instance
cost_monitor = CostMonitor(daily_limit_usd=5.0)