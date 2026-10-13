"""Cheap input revisions for full overlay publication; activity stays independent."""
import json
from pathlib import Path
from fc27_academy.paths import BRIDGE_ROOT, ACADEMY_STATE_ROOT, EVENTS_ROOT, USER_ROOT, CONFIG_ROOT, PROJECT_ROOT
from fc27_academy.runtime_config import career_settings_path

def stamp(path):
    try:
        st=Path(path).stat();return (st.st_mtime_ns,st.st_size)
    except OSError:return None

def revision(life,game_pid,activity=None,runtime_override=None):
    key=str(life.get('storage_key') or '')
    paths=[BRIDGE_ROOT/'active_context.lua', BRIDGE_ROOT/'overlay_view.json',USER_ROOT/'manager_settings.json',CONFIG_ROOT/'academy_settings.json',PROJECT_ROOT/'data/academy_settings.default.json']
    if key:
        paths += [ACADEMY_STATE_ROOT/'saves'/key/'generated_world.json',EVENTS_ROOT/key/'events.json',career_settings_path(key)]
    # Generation and wall-clock timestamps are publisher outputs, not new inputs.
    lifecycle={k:life.get(k) for k in ('state','detail','runtime_session','career_uid','storage_key','branch_id','request_id','career_date','snapshot_sequence')}
    act={k:(activity or {}).get(k) for k in ('state','task','trigger','request_id','stage','detail','stage_index','stage_total')}
    return (game_pid,json.dumps(lifecycle,sort_keys=True),json.dumps(act,sort_keys=True),json.dumps(runtime_override or {},sort_keys=True),tuple(stamp(p) for p in paths))
