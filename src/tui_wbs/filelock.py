"""File locking for concurrent access prevention."""

from __future__ import annotations

import os
import time
from pathlib import Path

MAX_LOCK_AGE = 3600  # 1 hour


def _lock_path(project_dir: Path) -> Path:
    return project_dir / ".tui-wbs" / ".lock"


def acquire_lock(project_dir: Path) -> bool:
    """Try to acquire a lock. Returns True if successful."""
    lock_file = _lock_path(project_dir)
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    if lock_file.exists():
        try:
            content = lock_file.read_text(encoding="utf-8").strip()
            parts = content.split("|")
            if len(parts) == 2:
                pid = int(parts[0])
                timestamp = float(parts[1])
                # Check if process is still alive
                try:
                    os.kill(pid, 0)
                    # Process exists, check age
                    if time.time() - timestamp > MAX_LOCK_AGE:
                        # Stale lock
                        lock_file.unlink()
                    else:
                        return False  # Lock held by live process
                except OSError:
                    # Process doesn't exist, stale lock
                    lock_file.unlink()
        except (ValueError, OSError):
            lock_file.unlink()

    # Write our lock
    lock_file.write_text(
        f"{os.getpid()}|{time.time()}", encoding="utf-8"
    )
    return True


def release_lock(project_dir: Path) -> None:
    """Release the lock."""
    lock_file = _lock_path(project_dir)
    try:
        if lock_file.exists():
            content = lock_file.read_text(encoding="utf-8").strip()
            parts = content.split("|")
            if len(parts) >= 1 and int(parts[0]) == os.getpid():
                lock_file.unlink()
    except (ValueError, OSError):
        pass


def is_locked(project_dir: Path) -> bool:
    """Check if the project is locked by another process."""
    lock_file = _lock_path(project_dir)
    if not lock_file.exists():
        return False
    try:
        content = lock_file.read_text(encoding="utf-8").strip()
        parts = content.split("|")
        if len(parts) == 2:
            pid = int(parts[0])
            if pid == os.getpid():
                return False  # Our own lock
            try:
                os.kill(pid, 0)
                timestamp = float(parts[1])
                return time.time() - timestamp <= MAX_LOCK_AGE
            except OSError:
                return False  # Dead process
    except (ValueError, OSError):
        pass
    return False
