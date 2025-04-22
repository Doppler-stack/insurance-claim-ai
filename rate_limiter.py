import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from auth import require_api_key

# Stores API call timestamps for each key - Key format: (ip, api_key)
call_log = defaultdict(list)  # Tracks request timestamps per (IP, key)
block_log = deque(maxlen=100)  # Keeps the last 100 blocked events

# Set max requests per minute per key
RATE_LIMIT = 30  # adjust as needed per-minute


def rate_limiter(request: Request, api_key: str = Depends(require_api_key)):
    client_ip = request.client.host or "unknown"  # fallback if no IP

    # Rate key: e.g. ("192.168.0.1", "abc123")
    rate_key = (client_ip, api_key)
    now = time.time()
    window_start = now - 60  # 60-second window

    # Clean up old entries
    recent_calls = [t for t in call_log[rate_key] if t > window_start]
    call_log[rate_key] = recent_calls

    if len(recent_calls) >= RATE_LIMIT:
        # Track blocked event
        block_log.append(
            {
                "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
                "ip": client_ip,
                "api_key": api_key,
                "reason": "Rate limit exceeded",
            }
        )
        logging.warning(f"[RATE_LIMIT] {client_ip} hit limit with key {api_key}")
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded — try again in a bit.",
        )

    # Log the new request
    call_log[rate_key].append(now)
    logging.debug(
        f"[RATE_LIMIT] IP={client_ip}, key={api_key} at {time.strftime('%X')}"
    )
