import time
import logging
from pathlib import Path
from functools import wraps
from smartflow.config import LOG_DIR

# Logging setup
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"smartflow.{name}")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        # Console
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(ch)
        # File
        fh = logging.FileHandler(LOG_DIR / "smartflow.log")
        fh.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(fh)
    return logger


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, calls_per_second: float):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0

    def wait(self):
        now = time.monotonic()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.monotonic()


def retry(max_attempts: int = 3, backoff: float = 2.0):
    """Decorator for retrying failed HTTP calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        sleep_time = backoff ** attempt
                        time.sleep(sleep_time)
            raise last_exc
        return wrapper
    return decorator
