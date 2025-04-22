import os

from fastapi import APIRouter, Depends, HTTPException

from auth import require_api_key
from rate_limiter import block_log

admin_router = APIRouter(prefix="/admin", tags=["Admin Tools"])


@admin_router.get("/rate-limit/logs")
def get_rate_limit_block_log(api_key: str = Depends(require_api_key)):
    """
    View recent IP/API key blocks due to rate limiting.
    Only visible to users with the ADMIN_KEY (if set).
    """
    admin_key = os.getenv("ADMIN_KEY")
    if admin_key and api_key != admin_key:
        raise HTTPException(status_code=403, detail="Not authorized to view block logs")

    return {"recent_blocked_attempts": list(block_log)}
