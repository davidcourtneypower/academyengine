"""Detect FC27 returning to its main menu from Live Editor's own log (v1.24.28).

FC27 sends no Career Mode event when the player exits to the main menu, so the Lua
runtime cannot see it. Live Editor, however, logs
    [LE::UnsupportedLeaguesManager::Load] Start
every time FC27 enters the main menu (and never while a career is being played; see
the 09-10-2026 logs). The bridge tails the newest Live Editor log for that line.
Loading a career then arrives as the usual Lua sequence (event 2 -> 29 -> 26).
"""
from __future__ import annotations
import time
from pathlib import Path

MENU_MARKER = b'[LE::UnsupportedLeaguesManager::Load] Start'


def _looks_like_le_logs(d: Path) -> bool:
    try:
        return d.is_dir() and any(p.suffix.lower() == '.log' for p in d.iterdir())
    except OSError:
        return False


def find_logs_dir() -> Path | None:
    """Live Editor's Logs folder (v1.0.3: no longer only via the program folder).

    The program folder is found from the running Live Editor process, which Windows hides
    when Live Editor runs as administrator and Academy Engine does not. So the search also
    tries the remembered folder, the program folder from settings, Live Editor's data
    folders (often the same folder), and remembers what it finds for next time.
    """
    try:
        from .settings_store import load as load_manager_settings, save as save_manager_settings
        settings = load_manager_settings() or {}
    except Exception:
        settings, save_manager_settings = {}, None
    # v1.0.4: the remembered folder is checked first and on its own; the wider search (process
    # list, data folders) only runs when it is missing, as the launcher asks every 30 seconds.
    remembered = settings.get('live_editor_logs')
    if remembered and _looks_like_le_logs(Path(remembered)):
        return Path(remembered)
    candidates: list[Path] = []
    try:
        from .live_editor_integration import discover_live_editor_root, all_live_editor_data_roots
        root = discover_live_editor_root(settings.get('live_editor_root') or None)
        if root: candidates.append(Path(root) / 'Logs')
        if settings.get('live_editor_root'): candidates.append(Path(settings['live_editor_root']) / 'Logs')
        for d in all_live_editor_data_roots(settings.get('live_editor_data_root') or None, binary_root=root):
            candidates.append(Path(d) / 'Logs')
    except Exception:
        pass
    seen = set()
    for c in candidates:
        k = str(c).lower()
        if k in seen: continue
        seen.add(k)
        if _looks_like_le_logs(c):
            if save_manager_settings and settings.get('live_editor_logs') != str(c):
                try: settings['live_editor_logs'] = str(c); save_manager_settings(settings)
                except Exception: pass
            return c
    return None


def _default_logs_dir() -> Path | None:
    return find_logs_dir()


class MenuWatch:
    def __init__(self, logs_dir_resolver=None, clock=time.monotonic, poll_interval=0.5, resolve_interval=30.0):
        self._resolve = logs_dir_resolver or _default_logs_dir
        self._clock = clock
        self._poll_interval = poll_interval
        self._resolve_interval = resolve_interval
        self._logs: Path | None = None
        self._next_resolve = 0.0
        self._next_poll = 0.0
        self._file: Path | None = None
        self._pos = 0
        self._tail = b''

    def _logs_dir(self) -> Path | None:
        now = self._clock()
        if self._logs is None and now >= self._next_resolve:
            self._next_resolve = now + self._resolve_interval
            try: self._logs = self._resolve()
            except Exception: self._logs = None
        return self._logs

    def poll(self) -> bool:
        """True when the main-menu marker was written since the previous poll."""
        now = self._clock()
        if now < self._next_poll:
            return False
        self._next_poll = now + self._poll_interval
        logs = self._logs_dir()
        if not logs:
            return False
        try:
            files = [p for p in logs.glob('*.log') if p.is_file()]
            newest = max(files, key=lambda p: p.stat().st_mtime) if files else None
        except (OSError, ValueError):
            return False
        if newest is None:
            return False
        try:
            size = newest.stat().st_size
        except OSError:
            return False
        if newest != self._file:
            # First file seen: only lines written from now on count. A newer file
            # (Live Editor starts one per day/session) is read from its start.
            self._pos = size if self._file is None else 0
            self._file = newest; self._tail = b''
        if size < self._pos:
            self._pos = 0; self._tail = b''
        if size == self._pos:
            return False
        try:
            with open(newest, 'rb') as f:
                f.seek(self._pos)
                chunk = f.read(min(size - self._pos, 8_000_000))
        except OSError:
            return False
        self._pos += len(chunk)
        data = self._tail + chunk
        self._tail = data[-(len(MENU_MARKER) - 1):]    # a marker split across two reads
        return MENU_MARKER in data
