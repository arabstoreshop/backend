import time
from collections import defaultdict
from threading import Lock

_hits: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def too_many_orders(key: str, limit: int = 8, window_sec: int = 600) -> bool:
    now = time.time()
    with _lock:
        stamps = [t for t in _hits[key] if now - t < window_sec]
        if len(stamps) >= limit:
            _hits[key] = stamps
            return True
        stamps.append(now)
        _hits[key] = stamps
        return False
