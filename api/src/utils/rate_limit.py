from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Deque, DefaultDict, Tuple


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


rate_limiter = InMemoryRateLimiter()
