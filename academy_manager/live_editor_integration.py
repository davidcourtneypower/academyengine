from __future__ import annotations
from pathlib import Path
import os, shutil
from .bridge import detect_live_editor_root

ROOT=Path(__file__).resolve().parents[1]
BOOTSTRAP=ROOT/'integration'/'lua'/'FC27_Academy_Engine_Autorun.lua'


def _looks_like_binary_root(p:Path|None)->bool:
    return bool(p and p.is_dir() and (p/'FCLiveEditor.DLL').exists() and (p/'Launcher.exe').exists())


def _looks_like_data_root(p:Path|None)->bool:
    if not p or not p.is_dir():
        return False
    # Live Editor's writable data root contains le_config.json and the lua folder.
    return (p/'le_config.json').exists() or (p/'lua').is_dir()


def discover_live_editor_root(configured:str|None=None):
    """Resolve Live Editor's binary folder without assuming an install location.

    A saved user selection wins. If Live Editor is already running, the process path
    is used. Otherwise the launcher asks the user to select the folder explicitly.
    """
    if configured:
        p=Path(configured).expanduser()
        if _looks_like_binary_root(p): return p
    running=detect_live_editor_root()
    if _looks_like_binary_root(running): return running
    return None

def _registry_data_roots():
    if os.name!='nt':
        return []
    out=[]
    try:
        import winreg
        base=winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'SOFTWARE\Live Editor')
    except Exception:
        return out
    def scan(key, depth=0):
        if depth>3: return
        try:
            i=0
            while True:
                try:
                    name,val,_=winreg.EnumValue(key,i); i+=1
                except OSError: break
                if str(name).lower().replace('_',' ').strip() in ('data dir','data directory','root dir','root directory'):
                    try:
                        p=Path(os.path.expandvars(str(val))).expanduser()
                        if p.is_dir(): out.append(p)
                    except Exception: pass
            j=0
            while True:
                try:
                    subname=winreg.EnumKey(key,j); j+=1
                    sub=winreg.OpenKey(key,subname)
                    scan(sub,depth+1)
                    sub.Close()
                except OSError: break
        except Exception:
            pass
    try:
        scan(base); base.Close()
    except Exception:
        pass
    # Stable de-dupe preserving order.
    seen=set(); result=[]
    for p in out:
        k=str(p).lower()
        if k not in seen:
            seen.add(k); result.append(p)
    return result


def _roots_from_le_logs(*dirs)->list[Path]:
    """Data roots Live Editor itself reported ("Load Config From <root>\\le_config.json").

    v1.24.12: the binary folder also contains a lua/ directory, so it used to be
    accepted as the data root and the autorun was installed where Live Editor never
    executes it (the user's logs kept showing the v1.24.02 bootstrap).
    """
    import re
    out=[]
    pat=re.compile(r'Load Config From (.+?)[\\/]le_config\.json',re.IGNORECASE)
    for d in dirs:
        if not d: continue
        logs=Path(d)/'Logs'
        try: files=sorted(logs.glob('*.log'),key=lambda f:f.stat().st_mtime,reverse=True)[:5]
        except OSError: continue
        for f in files:
            try: text=f.read_text(encoding='utf-8',errors='replace')
            except OSError: continue
            for m in reversed(pat.findall(text)):
                p=Path(m.strip())
                if p not in out: out.append(p)
    return out


def _default_data_roots()->list[Path]:
    out=[]
    drive=os.environ.get('SystemDrive','C:')
    for base in (Path(drive+'\\'), Path.home()/'Documents'):
        out.append(base/'FC 27 Live Editor')
    return out


def _data_root_candidates(configured:str|None=None, binary_root:Path|str|None=None)->list[Path]:
    candidates=[]
    if configured: candidates.append(Path(configured))
    candidates.extend(_roots_from_le_logs(binary_root))
    candidates.extend(_registry_data_roots())
    candidates.extend(_default_data_roots())
    if binary_root: candidates.append(Path(binary_root))   # self-contained installs: last resort
    seen=set(); out=[]
    for p in candidates:
        try:
            p=Path(os.path.expandvars(str(p))).expanduser()
            k=str(p).lower()
            if k in seen: continue
            seen.add(k)
            if _looks_like_data_root(p): out.append(p)
        except Exception:
            continue
    # A folder that actually holds le_config.json beats one that merely has lua/.
    return sorted(out,key=lambda p:0 if (p/'le_config.json').exists() else 1)


def discover_live_editor_data_root(configured:str|None=None, binary_root:Path|str|None=None):
    """Find Live Editor's writable data root (where le_config.json and lua/autorun live)."""
    c=_data_root_candidates(configured,binary_root)
    return c[0] if c else None


def all_live_editor_data_roots(configured:str|None=None, binary_root:Path|str|None=None)->list[Path]:
    return _data_root_candidates(configured,binary_root)


def ensure_autorun_installed(le_data_root:Path|str|None, extra_roots=()):
    """Install/refresh the bootstrap in the data root and any other plausible root.

    Installing in more than one folder is safe: the bootstrap guards itself with a
    process-wide flag, so only the copy Live Editor executes first does anything.
    """
    le_data_root=Path(le_data_root) if le_data_root else None
    if not le_data_root or not le_data_root.is_dir() or not BOOTSTRAP.exists():
        return {'ok':False,'reason':'LIVE_EDITOR_DATA_ROOT_UNKNOWN'}
    roots=[le_data_root]+[Path(r) for r in extra_roots if Path(r)!=le_data_root]
    installed=[]; updated=False; errors=[]
    for root in roots:
        try:
            autorun=root/'lua'/'autorun'
            autorun.mkdir(parents=True,exist_ok=True)
            target=autorun/'FC27_Academy_Engine.lua'
            changed=not target.exists() or target.read_bytes()!=BOOTSTRAP.read_bytes()
            if changed: shutil.copy2(BOOTSTRAP,target)
            updated=updated or changed; installed.append(str(target))
        except Exception as exc:
            errors.append(f'{root}: {exc}')
    if not installed:
        return {'ok':False,'reason':'; '.join(errors) or 'install failed','data_root':str(le_data_root)}
    return {'ok':True,'updated':updated,'path':installed[0],'paths':installed,'data_root':str(le_data_root),'errors':errors}
