from fc27_academy.fsutil import replace_retry
import json, os
from fc27_academy.paths import USER_ROOT
DEFAULT={'live_editor_root':'','live_editor_data_root':'','ui_theme':'dark','overlay_hotkey':'F8','controller_enabled':True,'controller_combo':'L3+R3','face_enabled':False,'face_library_path':'','face_write_ingame':False}

def path(): return USER_ROOT/'manager_settings.json'

def load():
    p=path()
    if not p.exists():return DEFAULT.copy()
    try:return {**DEFAULT,**json.loads(p.read_text(encoding='utf-8'))}
    except Exception:return DEFAULT.copy()

def save(data):
    p=path();p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');replace_retry(tmp,p)
