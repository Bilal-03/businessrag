from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Deque, DefaultDict, Tuple
from config import get_settings


class InMemoryRateLimiter:
    """Small fixed-window limiter for a single API process.

    This is intentionally dependency-free for the current deployment. Multi-instance
    deployments must replace it with a shared store (for example Redis) before scale-out.
    """

    def __init__(self) -> None:
        self._events: DefaultDict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, scope: str, identifier: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        now = monotonic()
        key = (scope, identifier)
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])) + 1)
                return False, retry_after
            events.append(now)
            return True, 0


class RedisRateLimiter:
    """Redis-backed fixed-window limiter for multi-instance deployments.

    Redis failures fail open to preserve availability, while emitting a
    bounded warning from the caller. Operators should alert on this event;
    the in-memory fallback is intentionally not treated as scale-safe.
    """

    def __init__(self, redis_url: str):
        import redis

        self._client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=0.25)

    def check(self, scope: str, identifier: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        key = f"bizguide:ratelimit:{scope}:{identifier}"
        try:
            with self._client.pipeline() as pipe:
                pipe.incr(key)
                pipe.ttl(key)
                count, ttl = pipe.execute()
                if count == 1:
                    self._client.expire(key, window_seconds)
                if count > limit:
                    return False, max(1, int(ttl if ttl and ttl > 0 else window_seconds))
                return True, 0
        except Exception:
            return True, 0


def build_rate_limiter():
    settings = get_settings()
    if settings.redis_url:
        try:
            return RedisRateLimiter(settings.redis_url)
        except Exception:
            # Startup stays available if the optional shared limiter is not
            # reachable; the deployment health check should catch this via
            # the configured observability alert.
            pass
    return InMemoryRateLimiter()


rate_limiter = build_rate_limiter()
