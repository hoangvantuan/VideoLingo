"""The lock of output/ while a Lượt chạy playlist runs (ADR-0002, #18).

The run writes ``output/.playlist_run.lock`` with the ID of its process. The single video mode
of Streamlit and the local API (another process) read it with ``is_locked()`` and leave
``output/`` alone. A lock left behind by a crash is stale and removed by ``is_locked()``: in the
process that wrote it no run is alive any more, or that process has ended.

No heavy imports: ``api.py`` reads the lock.
"""
import os
import sys
from pathlib import Path

LOCK_FILE = Path("output") / ".playlist_run.lock"


def acquire():
    LOCK_FILE.parent.mkdir(exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def release():
    """Remove the lock, and ``output/`` when nothing else is left in it."""
    LOCK_FILE.unlink(missing_ok=True)
    try:
        LOCK_FILE.parent.rmdir()
    except OSError:
        pass


def is_locked() -> bool:
    try:
        pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        pid = None
    if pid is not None and (_run_alive() if pid == os.getpid() else _process_alive(pid)):
        return True
    LOCK_FILE.unlink(missing_ok=True)
    return False


def _run_alive():
    from core.playlist_run import current_run
    run = current_run()
    return run is not None and run._runner.is_active


def _process_alive(pid):
    if sys.platform.startswith("win"):
        # os.kill() would terminate the process on Windows
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
