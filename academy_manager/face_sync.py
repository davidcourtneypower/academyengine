"""Background driver for the experimental in-game face writer (v1.24.31).

Called from the bridge loop once the overlay is READY. Work runs on a daemon thread,
one job at a time, and only when something relevant changed: the loaded career,
its last checkpoint, the face settings or the library folder.
"""
from __future__ import annotations

import threading
import time

from fc27_academy import face_ingame
from fc27_academy.faces import face_settings
from .settings_store import load as load_manager_settings

_lock = threading.Lock()
_running = False
_last_sig = None
_last_start = -1e9
MIN_INTERVAL = 30.0


def _roots(mgr: dict) -> list:
    roots = []
    try:
        from .live_editor_integration import discover_live_editor_root, discover_live_editor_data_root
        b = discover_live_editor_root(mgr.get('live_editor_root') or None)
        if b:
            roots.append(b)
        d = discover_live_editor_data_root(mgr.get('live_editor_data_root') or None, b)
        if d:
            roots.append(d)
    except Exception:
        pass
    return roots


def _job(world, fs, roots, log):
    global _running
    try:
        res = face_ingame.sync(world or {}, fs.get('face_library_path'), roots,
                               enabled=bool(fs.get('face_enabled') and fs.get('face_write_ingame')))
        if log and (res['written'] or res['removed'] or res['errors'] or res['skipped_user_files']):
            log(f"FC27AE_FACES ingame written={res['written']} kept={res['kept']} removed={res['removed']} "
                f"user_files_left={res['skipped_user_files']} errors={res['errors']} reason={res['reason'] or '-'}")
    except Exception as exc:
        if log:
            log(f'FC27AE_FACES ingame ERROR {type(exc).__name__}: {exc}')
    finally:
        with _lock:
            _running = False


def tick(world: dict | None, log=None, *, wait: bool = False) -> bool:
    """Start a sync if needed. Returns True when a job was started."""
    global _running, _last_sig, _last_start
    fs = face_settings()
    want = bool(fs.get('face_enabled') and fs.get('face_write_ingame'))
    has_files = face_ingame.MANIFEST.exists() and face_ingame.MANIFEST.stat().st_size > 20
    if not want and not has_files:
        return False
    w = world or {}
    if want and not w.get('players'):
        return False   # no career loaded: never mirror an empty world
    sig = (want, fs.get('face_library_path'), w.get('storage_key'), w.get('last_checkpoint_id'),
           len(w.get('players') or {}))
    with _lock:
        if _running or sig == _last_sig or time.monotonic() - _last_start < MIN_INTERVAL:
            return False
        _running = True
        _last_sig = sig
        _last_start = time.monotonic()
    roots = _roots(load_manager_settings())
    t = threading.Thread(target=_job, args=(w, fs, roots, log), name='fc27ae-faces', daemon=True)
    t.start()
    if wait:
        t.join()
    return True
