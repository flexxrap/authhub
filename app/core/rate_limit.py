from fastapi import HTTPException, Request, status

from app.core import redis as redis_module

# brute-force protection on auth endpoints, not a general API rate limit
RATE_LIMIT = 5
RATE_WINDOW_SECONDS = 60


async def rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"ratelimit:{request.url.path}:{ip}"

    count = await redis_module.redis_client.incr(key)
    if count == 1:
        await redis_module.redis_client.expire(key, RATE_WINDOW_SECONDS)

    if count > RATE_LIMIT:
        ttl = await redis_module.redis_client.ttl(key)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests",
            headers={"Retry-After": str(ttl if ttl > 0 else RATE_WINDOW_SECONDS)},
        )
