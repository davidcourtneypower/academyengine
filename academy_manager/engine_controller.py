from __future__ import annotations
from fc27_academy.fsutil import replace_retry
import json, os, shutil, subprocess, sys, time
from pathlib import Path

try:
    import psutil
except Exception:
    psutil=None

ROOT=Path(__file__).resolve().parents[1]
from fc27_academy.paths import BRIDGE_ROOT
PID_FILE=BRIDGE_ROOT/'manager_bridge.pid'
RUNTIME_SRC=ROOT/'integration'/'lua'/'FC27_Academy_Engine_Runtime.lua'
RUNTIME_DST=BRIDGE_ROOT/'runtime_current.lua'
ENABLE_LEASE=BRIDGE_ROOT/'engine_enabled.lease'


def _alive(pid:int)->bool:
    if pid<=0:return False
    if psutil:
        try:return psutil.Process(pid).is_running()
        except Exception:return False
    try:
        os.kill(pid,0);return True
    except Exception:return False


def _prepare_runtime_file():
    """Stage the resident Lua before Live Editor can load the autorun bootstrap."""
    BRIDGE_ROOT.mkdir(parents=True,exist_ok=True)
    if not RUNTIME_SRC.exists():return {'ok':False,'error':f'Missing {RUNTIME_SRC.name}'}
    try:
        tmp=RUNTIME_DST.with_suffix(RUNTIME_DST.suffix+'.tmp')
        shutil.copy2(RUNTIME_SRC,tmp);replace_retry(tmp,RUNTIME_DST)
        return {'ok':True,'path':str(RUNTIME_DST)}
    except Exception as exc:return {'ok':False,'error':str(exc)}




def _write_enable_lease():
    """Publish a short-lived lease proving the companion bridge is intentionally enabled."""
    BRIDGE_ROOT.mkdir(parents=True,exist_ok=True)
    tmp=ENABLE_LEASE.with_suffix('.lease.tmp')
    tmp.write_text(str(int(time.time())),encoding='utf-8')
    replace_retry(tmp,ENABLE_LEASE)

def _clear_enable_lease():
    try: ENABLE_LEASE.unlink(missing_ok=True)
    except Exception: pass


def bridge_pid():
    try:
        pid=int(PID_FILE.read_text().strip())
        return pid if _alive(pid) else None
    except Exception:return None


def _startup_log_path():
    from fc27_academy.paths import LOG_ROOT
    LOG_ROOT.mkdir(parents=True,exist_ok=True)
    return LOG_ROOT/'bridge_startup.log'


def _tail(path:Path, limit:int=1600)->str:
    try:
        data=path.read_text(encoding='utf-8',errors='replace')
        return data[-limit:].strip()
    except Exception:
        return ''


def health():
    p=BRIDGE_ROOT/'bridge_state.json'
    state={}
    if p.exists():
        try:state=json.loads(p.read_text(encoding='utf-8'))
        except Exception:state={}
    fresh=False; age=None
    try:
        age=max(0.0,time.time()-p.stat().st_mtime);fresh=age<4.0
    except Exception:pass
    pid=bridge_pid(); alive=bool(pid)
    logp=_startup_log_path()
    return {'running':bool(fresh or alive),'fresh':fresh,'state_age':age,'pid':pid,'pid_alive':alive,'state':state,'root':str(BRIDGE_ROOT),'runtime_file':str(RUNTIME_DST),'runtime_ready':RUNTIME_DST.exists(),'startup_log':str(logp),'startup_error':_tail(logp) if not (fresh or alive) else ''}


def start(debug=False):
    _write_enable_lease()
    prep=_prepare_runtime_file()
    if not prep.get('ok'):
        _clear_enable_lease()
        return {'ok':False,'status':'RUNTIME_STAGE_FAILED','error':prep.get('error')}
    h=health()
    if h['running']:return {'ok':True,'status':'ALREADY_RUNNING','pid':h.get('pid'),'runtime':prep.get('path')}
    # Prefer console python.exe + CREATE_NO_WINDOW (invisible, and stdout/stderr are
    # captured to bridge_startup.log). The launcher itself normally runs under
    # pythonw.exe (via "pyw"), so map that to the sibling python.exe when present.
    exe_path=Path(sys.executable)
    if exe_path.name.lower()=='pythonw.exe' and (exe_path.parent/'python.exe').exists():
        exe_path=exe_path.parent/'python.exe'
    exe=str(exe_path)
    cmd=[exe,str(ROOT/'run_bridge_service.py')]
    if debug:cmd.append('--debug')
    flags=0
    if os.name=='nt' and not debug:flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    logp=_startup_log_path()
    from fc27_academy.fsutil import cap_log
    cap_log(logp)
    try:
        with logp.open('a',encoding='utf-8') as log:
            log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] launch: {' '.join(cmd)}\n")
            log.flush()
            env=os.environ.copy(); env['FC27AE_OWNER_PID']=str(os.getpid())
            proc=subprocess.Popen(cmd,cwd=str(ROOT),creationflags=flags,stdout=log,stderr=log,env=env)
        PID_FILE.write_text(str(proc.pid),encoding='utf-8')
        time.sleep(0.18)
        rc=proc.poll()
        if rc is not None:
            PID_FILE.unlink(missing_ok=True)
            _clear_enable_lease()
            return {'ok':False,'status':'PROCESS_EXITED','error':f'Bridge exited immediately with code {rc}. '+_tail(logp),'runtime':prep.get('path')}
        return {'ok':True,'status':'STARTED','pid':proc.pid,'runtime':prep.get('path')}
    except Exception as exc:
        _clear_enable_lease()
        return {'ok':False,'status':'START_FAILED','error':str(exc),'runtime':prep.get('path')}


_LAST_RECOVERY_AT=0.0
def ensure_running(debug=False, retry_seconds=4.0):
    global _LAST_RECOVERY_AT
    h=health()
    if h.get('running'):
        return {'ok':True,'status':'RUNNING','health':h}
    now=time.monotonic()
    if now-_LAST_RECOVERY_AT < retry_seconds:
        return {'ok':False,'status':'RECOVERY_BACKOFF','health':h,'error':h.get('startup_error','')}
    _LAST_RECOVERY_AT=now
    PID_FILE.unlink(missing_ok=True)
    result=start(debug=debug)
    result['health']=health()
    return result

def stop():
    _clear_enable_lease()
    pid=bridge_pid()
    if not pid:return {'ok':True,'status':'NOT_RUNNING'}
    try:
        if psutil:
            p=psutil.Process(pid);p.terminate()
            try:p.wait(timeout=3)
            except Exception:p.kill()
        else:os.kill(pid,15)
        PID_FILE.unlink(missing_ok=True)
        return {'ok':True,'status':'STOPPED','pid':pid}
    except Exception as exc:return {'ok':False,'status':'ERROR','error':str(exc),'pid':pid}
