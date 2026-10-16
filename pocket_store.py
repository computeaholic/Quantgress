"""Controlled single-writer access for the local Pocket research database.

DuckDB supports one writing process.  This module makes that operational
constraint explicit instead of relying on whichever process opens the file
first.  The lock is adjacent to the database and contains only process
metadata; no account or research data is written to it.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import time
from pathlib import Path

import duckdb


class WriterBusy(RuntimeError):
    """Raised when another process owns the DuckDB writer lock."""


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _remove_stale_lock(lock_path: Path) -> bool:
    """Remove a lock owned by a dead process on this host.

    Corrupt locks and locks from another host fail closed.  They require
    manual inspection rather than an automated deletion that could admit a
    second writer.
    """

    try:
        owner = json.loads(lock_path.read_text())
    except (OSError, ValueError, TypeError):
        return False
    if owner.get("hostname") != socket.gethostname():
        return False
    pid = owner.get("pid")
    if not isinstance(pid, int) or _pid_is_running(pid):
        return False
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    return True


@contextlib.contextmanager
def single_writer(db_path, timeout: float = 10.0, poll_interval: float = 0.1):
    """Yield one read/write DuckDB connection or fail closed.

    The interface owns lock acquisition, connection lifetime, and cleanup.
    Callers cannot accidentally open a second write connection behind it.
    """

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(f"{path}.lock")
    deadline = time.monotonic() + max(timeout, 0)
    fd = None

    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if _remove_stale_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise WriterBusy(f"DuckDB writer already active: {lock_path}")
            time.sleep(poll_interval)

    con = None
    try:
        owner = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        os.write(fd, json.dumps(owner, sort_keys=True).encode("utf-8"))
        os.fsync(fd)
        con = duckdb.connect(str(path))
        yield con
    finally:
        if con is not None:
            con.close()
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
