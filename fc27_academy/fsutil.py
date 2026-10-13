"""Windows-safe atomic file replacement (v1.24.10).

On Windows, os.replace() fails with PermissionError (WinError 5/32) while any other
process has the destination open without FILE_SHARE_DELETE: the overlay DLL, the
Live Editor Lua adapter (fopen), the launcher's Python reads, antivirus or the
search indexer. Readers hold files for milliseconds, so a short bounded retry turns
a crash-the-loop error (seen in bridge.log) into a brief wait.
"""
from __future__ import annotations
import os, time
from pathlib import Path

_DELAYS = (0.005, 0.01, 0.02, 0.03, 0.05, 0.05, 0.1, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5)  # ~2.2s total


def replace_retry(src, dst) -> None:
    last = None
    for delay in (0.0,) + _DELAYS:
        if delay:
            time.sleep(delay)
        try:
            os.replace(src, dst)
            return
        except PermissionError as exc:  # sharing violation / access denied while open
            last = exc
        except OSError as exc:
            if getattr(exc, 'winerror', None) in (5, 32, 33):
                last = exc
            else:
                raise
    raise last


def write_text_atomic(path, text: str, encoding: str = 'utf-8') -> None:
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text, encoding=encoding)
    replace_retry(tmp, path)


def cap_log(path, max_bytes: int = 2_000_000) -> None:
    """Keep an append-only log bounded (v1.24.38): past ``max_bytes`` it becomes ``<name>.1``."""
    try:
        p = Path(path)
        if p.exists() and p.stat().st_size >= max_bytes:
            replace_retry(p, p.with_name(p.name + '.1'))
    except Exception:
        pass
