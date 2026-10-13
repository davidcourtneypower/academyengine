from __future__ import annotations

"""External overlay host lifecycle.

v1.24 never injects Academy UI code into FC27.exe. AcademyOverlayHost.exe is a
separate process (since v1.0.6 one program, no DLL) which draws the overlay and follows
FC27's top-level window using the GAME_PID published by Python.

v1.24.09 also treats the native renderer heartbeat as authoritative. A helper
process that exists without a live renderer is not considered healthy and is
restarted automatically.
"""

import atexit
import os
import subprocess
import time
from pathlib import Path

import psutil

from fc27_academy.paths import BRIDGE_ROOT, LOG_ROOT, ensure_dirs

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'native_overlay' / 'AcademyOverlayHost.exe'
HEARTBEAT = BRIDGE_ROOT / 'overlay_host_heartbeat.txt'
LOG_FILE = LOG_ROOT / 'overlay_host.log'
_PROC: subprocess.Popen | None = None
_LAST_RESULT: dict = {}
_LAST_ATTEMPT = 0.0
_HOST_STARTED_AT = 0.0
_STALE_CLEANED = False


def _alive() -> bool:
    return bool(_PROC is not None and _PROC.poll() is None)


def _heartbeat_fresh(*, max_age: float = 3.5) -> bool:
    try:
        return HEARTBEAT.exists() and (time.time() - HEARTBEAT.stat().st_mtime) <= max_age
    except OSError:
        return False


def _terminate_stale_hosts() -> None:
    """Remove orphan helper processes from older launcher sessions.

    AcademyOverlayHost.exe is owned exclusively by Academy Engine, so a stale
    copy is never useful. This also prevents a dead renderer/mutex from making
    a newly spawned helper look healthy while F8 has no listener.
    """
    global _STALE_CLEANED
    if _STALE_CLEANED or os.name != 'nt':
        return
    _STALE_CLEANED = True
    current_pid = _PROC.pid if _alive() else None
    victims=[]
    for proc in psutil.process_iter(['pid','name','exe']):
        try:
            if current_pid and proc.pid == current_pid:
                continue
            name=(proc.info.get('name') or '').lower()
            exe=Path(proc.info.get('exe') or '').name.lower() if proc.info.get('exe') else ''
            if name == HOST.name.lower() or exe == HOST.name.lower():
                proc.terminate(); victims.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    if victims:
        _,alive=psutil.wait_procs(victims,timeout=1.0)
        for proc in alive:
            try: proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError): pass
    try: HEARTBEAT.unlink(missing_ok=True)
    except OSError: pass


def _stop_process() -> None:
    global _PROC
    p=_PROC; _PROC=None
    if p is not None and p.poll() is None:
        try:
            p.terminate(); p.wait(timeout=1.5)
        except Exception:
            try: p.kill()
            except Exception: pass


def ensure_running(*, retry_seconds: float = 1.0) -> dict:
    global _PROC, _LAST_RESULT, _LAST_ATTEMPT, _HOST_STARTED_AT
    ensure_dirs()
    now=time.monotonic()
    if _alive():
        # Give the freshly started renderer a short grace period to create the worker
        # and heartbeat file. After that, process-alive without heartbeat means
        # the renderer died and the helper must be recycled.
        if _heartbeat_fresh() or (now-_HOST_STARTED_AT) < 2.5:
            detail='External overlay host and F8 listener running' if _heartbeat_fresh() else 'External overlay host starting renderer…'
            return {'ok': True, 'status': 'RUNNING', 'pid': _PROC.pid, 'heartbeat': _heartbeat_fresh(), 'detail': detail}
        _stop_process()
        _LAST_RESULT={'ok':False,'status':'HOST_HEARTBEAT_LOST','detail':'Overlay renderer heartbeat stopped; restarting external host'}

    if now-_LAST_ATTEMPT < retry_seconds and _LAST_RESULT:
        return dict(_LAST_RESULT)
    _LAST_ATTEMPT=now
    if os.name != 'nt':
        _LAST_RESULT={'ok':False,'status':'WINDOWS_ONLY','detail':'External overlay host starts only on Windows'}
        return dict(_LAST_RESULT)
    if not HOST.exists():
        _LAST_RESULT={'ok':False,'status':'MISSING_COMPONENT','detail':f'Missing {HOST.name}'}
        return dict(_LAST_RESULT)

    _terminate_stale_hosts()
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    log_handle=None
    try:
        LOG_FILE.parent.mkdir(parents=True,exist_ok=True)
        from fc27_academy.fsutil import cap_log
        cap_log(LOG_FILE)
        try:
            log_handle=open(LOG_FILE,'ab',buffering=0)
        except OSError:
            log_handle=subprocess.DEVNULL
        try: HEARTBEAT.unlink(missing_ok=True)
        except OSError: pass
        _PROC=subprocess.Popen(
            [str(HOST)],cwd=str(HOST.parent),creationflags=flags,
            stdin=subprocess.DEVNULL,stdout=log_handle,stderr=log_handle,
        )
        _HOST_STARTED_AT=time.monotonic()
        time.sleep(0.10)
        if _PROC.poll() is not None:
            code=_PROC.returncode; _PROC=None
            _LAST_RESULT={'ok':False,'status':'HOST_EXITED','detail':f'External overlay host exited with code {code}; see {LOG_FILE}'}
        else:
            _LAST_RESULT={'ok':True,'status':'RUNNING','pid':_PROC.pid,'heartbeat':False,'detail':'External overlay host starting renderer…'}
    except Exception as exc:
        _PROC=None
        _LAST_RESULT={'ok':False,'status':'HOST_ERROR','detail':str(exc)}
    finally:
        if log_handle not in (None,subprocess.DEVNULL):
            try: log_handle.close()
            except Exception: pass
    return dict(_LAST_RESULT)


def status() -> dict:
    if _alive():
        hb=_heartbeat_fresh()
        return {'ok':hb or (time.monotonic()-_HOST_STARTED_AT)<2.5,'status':'RUNNING' if hb else 'STARTING','pid':_PROC.pid,'heartbeat':hb,'detail':'External overlay host and F8 listener running' if hb else 'External overlay host starting renderer…'}
    return dict(_LAST_RESULT or {'ok':False,'status':'STOPPED','detail':'External overlay host is stopped'})


def stop() -> None:
    global _LAST_RESULT
    _stop_process()
    try: HEARTBEAT.unlink(missing_ok=True)
    except OSError: pass
    _LAST_RESULT={'ok':False,'status':'STOPPED','detail':'External overlay host stopped'}


def reset() -> None:
    stop()


atexit.register(stop)
