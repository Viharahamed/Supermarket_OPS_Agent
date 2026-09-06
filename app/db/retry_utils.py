"""Utility to retry functions when SQLite reports a locked database.

Provides a @retry_on_lock decorator that catches ``sqlite3.OperationalError`` with
"database is locked" messages and retries the wrapped function with exponential
back‑off up to a maximum number of attempts.
"""

import time
import sqlite3
import functools
from typing import Callable, TypeVar, Any, cast

from app.exceptions import DatabaseLockedError

_T = TypeVar("_T")


def retry_on_lock(max_retries: int = 3, backoff_factor: float = 0.5) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """Decorator to retry a callable when SQLite lock errors occur.

    Args:
        max_retries: Maximum number of retry attempts (default 3).
        backoff_factor: Base back‑off in seconds; each retry waits
            ``backoff_factor * (2 ** attempt)`` seconds.
    """

    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> _T:
            attempt = 0
            while True:
                try:
                    return cast(_T, func(*args, **kwargs))
                except Exception as exc:
                    if "database is locked" in str(exc).lower():
                        if attempt >= max_retries:
                            raise DatabaseLockedError(str(exc)) from exc
                        time.sleep(backoff_factor * (2 ** attempt))
                        attempt += 1
                        continue
                    raise
        return wrapper

    return decorator
