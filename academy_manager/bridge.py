from __future__ import annotations
from pathlib import Path
import json, time, os

from fc27_academy.paths import BRIDGE_ROOT

_CACHE_AT=0.0
_CACHE_ROWS=[]
_DLL_AT=0.0
_DLL_DETECTED=False
_DLL_PID=None
_ELEV_CACHE=(None,0.0,False)

# Only these processes need their (expensive) exe path and command line.
_INTERESTING=('fc27','launcher','liveeditor','fc27le')


def _proc_rows():
    global _CACHE_AT,_CACHE_ROWS
    now=time.monotonic()
    if now-_CACHE_AT<1.0:return _CACHE_ROWS
    try:
        import psutil
        rows=[]
        # v1.24.10: list names only, and query exe/cmdline just for the handful of
        # candidate processes. Fetching the command line of every process on the
        # system once a second (from both the launcher UI thread and the bridge
        # loop) was the bulk of the cost.
        for p in psutil.process_iter(['pid','name']):
            try:
                info=p.info; name=str(info.get('name') or '')
                row={'pid':info.get('pid'),'name':name,'exe':'','cmdline':''}
                low=name.lower().replace(' ','').replace('_','')
                if any(k in low for k in _INTERESTING):
                    try: row['exe']=str(p.exe() or '')
                    except Exception: pass
                    try: row['cmdline']=' '.join(p.cmdline() or [])
                    except Exception: pass
                rows.append(row)
            except Exception:continue
        _CACHE_ROWS=rows;_CACHE_AT=now;return rows
    except Exception:
        _CACHE_ROWS=[];_CACHE_AT=now;return []


def _game_row():
    """Return the actual FC27 game process, not EA/launcher helper processes.

    Match the actual FC27 game process and avoid launcher/helper processes.
    """
    rows=_proc_rows()
    for r in rows:
        n=r['name'].lower().replace(' ','')
        if n in ('fc27.exe','fc27'):
            return r
    return None


def detect_game():
    return _game_row() is not None


def game_pid():
    r=_game_row(); return int(r['pid']) if r and r.get('pid') else None


def live_editor_process():
    """Return only an actual Live Editor launcher process.

    FC27 can inherit the injector/DLL path in its command line, which made the
    game itself look like a launcher forever after the real Launcher.exe exited.
    """
    game=game_pid()
    for r in _proc_rows():
        if game and int(r.get('pid') or 0)==int(game):
            continue
        name=(r.get('name') or '').lower()
        exe_name=Path(r.get('exe') or '').name.lower()
        compact=(name+' '+exe_name).replace(' ','').replace('_','')
        if name=='launcher.exe' or exe_name=='launcher.exe':
            blob=(str(r.get('exe') or '')+' '+str(r.get('cmdline') or '')).lower().replace(' ','')
            if 'liveeditor' in blob or 'fcliveeditor' in blob or 'fc27le' in blob:
                return r
        if 'liveeditor' in compact or compact.startswith('fc27le'):
            return r
    return None

def _dll_in_game():
    """Best-effort direct check for FCLiveEditor.DLL in FC27.

    This can be blocked when FC27 runs elevated and Academy Engine does not, so
    it is evidence, not the sole source of truth.
    """
    global _DLL_AT,_DLL_DETECTED,_DLL_PID
    now=time.monotonic()
    row=_game_row()
    if not row:
        _DLL_PID=None;_DLL_DETECTED=False;return False
    pid=int(row['pid'])
    # A loaded DLL stays loaded for the life of the process: once found, remember
    # it per PID. Until found, walk the module list at most every 30 s (it is
    # expensive on a large game process); v1.24.09 walked it every 4 s, twice.
    if pid==_DLL_PID and (_DLL_DETECTED or now-_DLL_AT<30.0):return _DLL_DETECTED
    _DLL_AT=now;_DLL_PID=pid;_DLL_DETECTED=False
    try:
        import psutil
        p=psutil.Process(int(row['pid']))
        for m in p.memory_maps(grouped=False):
            if str(getattr(m,'path','')).lower().endswith('fcliveeditor.dll'):
                _DLL_DETECTED=True;break
    except Exception:
        pass
    return _DLL_DETECTED


def elevation_mismatch() -> bool:
    """True when FC27 runs at a higher integrity level than Academy Engine.

    Academy Engine does not itself need administrator rights: the bridge only uses
    files under %LOCALAPPDATA%. But Windows blocks a non-elevated overlay from
    taking focus / receiving input over an elevated game window, and process
    inspection is denied. Detected by OpenProcess(QUERY_INFORMATION|VM_READ)
    failing with ERROR_ACCESS_DENIED while we are not elevated.
    """
    global _ELEV_CACHE
    row=_game_row()
    if not row or os.name!='nt': return False
    pid=int(row['pid']); now=time.monotonic()
    if _ELEV_CACHE[0]==pid and now-_ELEV_CACHE[1]<15.0: return _ELEV_CACHE[2]
    result=False
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            k32=ctypes.WinDLL('kernel32',use_last_error=True)
            k32.OpenProcess.restype=ctypes.c_void_p
            h=k32.OpenProcess(0x0400|0x0010,False,pid)
            if h: k32.CloseHandle(ctypes.c_void_p(h))
            else: result=ctypes.get_last_error()==5
    except Exception:
        result=False
    _ELEV_CACHE=(pid,now,result)
    return result


def _game_started_at():
    row=_game_row()
    if not row:return None
    try:
        import psutil
        return float(psutil.Process(int(row['pid'])).create_time())
    except Exception:
        return None


def _marker(name:str, max_age:float|None=None, current_game_only:bool=False):
    p=BRIDGE_ROOT/name
    try:
        st=p.stat(); age=max(0.0,time.time()-st.st_mtime)
        if max_age is not None and age>max_age:return None
        if current_game_only:
            started=_game_started_at()
            # Marker evidence is valid for the whole FC27 process lifetime, not just
            # for 30 seconds. Reject markers left by an older FC27 process instead.
            if started is not None and st.st_mtime < (started-3.0):
                return None
        data={'path':str(p),'age_seconds':age}
        try:data.update(json.loads(p.read_text(encoding='utf-8')))
        except Exception:pass
        return data
    except Exception:return None


def clear_live_session_markers():
    """Clear only transient evidence from the previous FC27 process.

    Persistent Academy career state is deliberately untouched. These files describe
    the injected Live Editor/Lua session and become invalid as soon as FC27 exits.
    """
    removed=[]
    for name in ('le_bootstrap_seen.json','resident_runtime_status.json','career_session_status.json'):
        p=BRIDGE_ROOT/name
        try:
            if p.exists():
                p.unlink(); removed.append(name)
        except Exception:
            pass
    return removed


def live_editor_status(configured_root:str|Path|None=None):
    launcher=live_editor_process()
    injected=_dll_in_game()
    game=detect_game()
    # Bootstrap marker proves that Live Editor's injected Lua environment ran our
    # autorun script. Runtime heartbeat proves the resident Academy runtime is alive.
    bootstrap=_marker('le_bootstrap_seen.json', current_game_only=bool(game))
    runtime=_marker('resident_runtime_status.json', current_game_only=bool(game))
    configured=False
    if configured_root:
        try:
            p=Path(configured_root); configured=p.is_dir() and (p/'FCLiveEditor.DLL').exists() and (p/'Launcher.exe').exists()
        except Exception:configured=False
    # Session evidence belongs to the current FC27 process only. A fresh marker can
    # linger for a few seconds after FC27 closes, but it must never keep the UI attached.
    runtime_state=str((runtime or {}).get('state') or '')
    runtime_live=bool(runtime and runtime_state not in {'DETACHED','NO_CAREER','LEFT_CAREER'})
    attached=bool(game and (runtime_live or injected or bootstrap))
    detected=bool(launcher or attached)
    if game and runtime_live:
        label='Resident runtime active'
    elif game and runtime and runtime_state=='DETACHED':
        label='Attached to FC27 — no Career Mode loaded'
    elif game and injected:
        label='Attached to FC27'
    elif game and bootstrap:
        label='Attached — runtime starting/waiting for Career Mode'
    elif launcher:
        label='Launcher running — handing off to FC27'
    elif configured and game:
        label='FC27 running — waiting for Live Editor autorun handshake'
    elif configured:
        label='Configured — not running'
    else:
        label='Not detected'
    return {
        'detected':detected,'attached':attached,'launcher_running':bool(launcher),
        'dll_visible':bool(injected),'bootstrap_seen':bootstrap,'runtime':runtime_live and runtime or None,'runtime_marker':runtime,
        'configured':configured,'game_running':game,'label':label,
    }


def detect_live_editor(configured_root:str|Path|None=None):
    return bool(live_editor_status(configured_root).get('detected'))


def detect_live_editor_root(configured_root:str|Path|None=None):
    r=live_editor_process()
    if r:
        exe=Path(r.get('exe') or '')
        if exe.exists():return exe.parent
    # If only the injected DLL is visible, infer its directory from the mapped module.
    row=_game_row()
    if row:
        try:
            import psutil
            p=psutil.Process(int(row['pid']))
            for m in p.memory_maps(grouped=False):
                path=Path(str(getattr(m,'path','')))
                if path.name.lower()=='fcliveeditor.dll' and path.exists():return path.parent
        except Exception:pass
    if configured_root:
        try:
            p=Path(configured_root)
            if p.is_dir() and (p/'FCLiveEditor.DLL').exists():return p
        except Exception:pass
    return None


def bridge_activity():
    p=BRIDGE_ROOT/'bridge_activity.json'
    try:
        data=json.loads(p.read_text(encoding='utf-8'))
        data['age_seconds']=max(0.0,time.time()-p.stat().st_mtime)
        return data
    except Exception:
        return {}


def is_game_foreground():
    """Best-effort Windows foreground check for the FC27 process.

    Used only to decide between an external Borderless overlay toast and a normal
    desktop notification. Failure is harmless and falls back to desktop delivery.
    """
    pid=game_pid()
    if not pid or os.name!='nt':
        return False
    try:
        import ctypes
        hwnd=ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:return False
        out=ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd,ctypes.byref(out))
        return int(out.value)==int(pid)
    except Exception:
        return False
