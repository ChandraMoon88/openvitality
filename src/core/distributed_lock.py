# src/core/distributed_lock.py
"""
Provides a locking mechanism to prevent race conditions.

Note: This implementation uses Python's `threading.Lock`, which is suitable
for a single-process, multi-threaded application. It is NOT a "distributed"
lock and will not work across multiple processes or multiple server instances.
For a multi-instance deployment (e.g., with Kubernetes or multiple uvicorn workers),
a shared locking mechanism like Redis (using SETNX) would be required.
"""
import threading
from contextlib import contextmanager

# A dictionary to hold locks for different resources
_locks: dict[str, threading.Lock] = {}
_master_lock = threading.Lock() # To protect access to the _locks dictionary

@contextmanager
def acquire_lock(lock_name: str, timeout: float = 30.0):
    """
    A context manager to acquire and release a lock.
    
    Usage:
        with acquire_lock('appointment:doctor123:2025-01-15-10:00'):
            # Critical section for booking
            ...
    """
    with _master_lock:
        if lock_name not in _locks:
            _locks[lock_name] = threading.Lock()
        lock = _locks[lock_name]

    acquired = lock.acquire(timeout=timeout)
    
    try:
        if not acquired:
            raise TimeoutError(f"Could not acquire lock for '{lock_name}' within {timeout} seconds.")
        yield
    finally:
        if acquired:
            lock.release()