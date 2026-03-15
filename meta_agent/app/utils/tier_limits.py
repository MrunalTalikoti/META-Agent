from datetime import date
from app.models.database import User, UserTier
from fastapi import HTTPException, status

TIER_LIMITS = {
    UserTier.FREE: 10,          # 10 requests/day
    UserTier.PRO: float('inf'),  # Unlimited
    UserTier.ENTERPRISE: float('inf')
}

def check_rate_limit(user: User, db):
    """Check if user has exceeded their tier limit"""
    
    # Reset counter if new day
    today = date.today()
    if user.last_request_date != today:
        user.requests_today = 0
        user.last_request_date = today
        db.commit()
    
    # Check limit
    limit = TIER_LIMITS[user.tier]
    if user.requests_today >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit exceeded. Upgrade to Pro for unlimited requests."
        )
    
    # Increment
    user.requests_today += 1
    db.commit()