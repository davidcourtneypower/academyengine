from __future__ import annotations
from fc27_academy.fsutil import replace_retry
import json, os, time
from pathlib import Path

from .live_data import (
    active_context, active_world, current_career, player_rows,
    clear_events_for_storage, delete_current_data, events_for_storage,
)
from .bridge import live_editor_status, detect_game, game_pid
from .settings_store import load as load_manager_settings, save as save_manager_settings
from .setting_definitions import SETTINGS, SETTINGS_GROUPS, LOCKED_INFO
from .ui_theme import tokens
from .controller import settings_view as controller_settings, PRESETS as CONTROLLER_PRESETS, normalize_combo, controller_help_text
from . import read_model
from fc27_academy.transaction_store import lifecycle as tx_lifecycle, publish_generation as tx_publish_generation, set_lifecycle as tx_set_lifecycle, generation_storage_key as tx_generation_storage_key
from fc27_academy.paths import BRIDGE_ROOT, LOG_ROOT
from fc27_academy.runtime_config import career_settings_path, debug_mode_available
from fc27_academy.settings import Settings as AcademySettings
from fc27_academy.playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK
from fc27_academy.role_sync import ROLE_ID_TO_LABEL
from fc27_academy import faces as face_lib
from .face_render import overlay_face_bmp

EXTRA_SETTINGS=[
 dict(ui_group='notifications',section='notifications',key='overlay_enabled',title='Overlay notifications',kind='bool',default=True,recommended='On',description='Master switch for Academy Engine play-time notification toasts. The main browser hotkey still works when these popups are disabled.'),
 dict(ui_group='notifications',section='notifications',key='playstyle_gained',title='PlayStyle acquired popup',kind='bool',default=True,recommended='On',description='Show a toast when an Academy Engine PlayStyle is successfully committed to FC27.'),
 dict(ui_group='notifications',section='notifications',key='playstyle_plus_gained',title='PlayStyle+ acquired popup',kind='bool',default=True,recommended='On',description='Show a toast when an eligible player receives their Academy Engine PlayStyle+.'),
 dict(ui_group='notifications',section='notifications',key='role_upgraded',title='Role++ acquired popup',kind='bool',default=True,recommended='On',description='Show a toast when Academy Engine successfully applies a verified Role++ upgrade.'),
 dict(ui_group='notifications',section='notifications',key='playstyle_lost',title='PlayStyle loss popup',kind='bool',default=True,recommended='On',description='Show a toast when an ageing player loses a PlayStyle or his PlayStyle+ drops back to the PlayStyle (for example Rapid+ to Rapid).'),
 dict(ui_group='notifications',section='notifications',key='only_user_team',title='Notifications only for my club',kind='bool',default=True,recommended='On',description='Limit play-time acquisition popups to players at your managed club. Events still records developments for all tracked generated players.'),
 dict(ui_group='notifications',section='notifications',key='popup_seconds',title='Notification duration',kind='int',minimum=3,maximum=20,step=1,suffix=' sec',default=6,recommended='5–8 sec',description='How long acquisition notification toasts remain visible before fading from the play-time overlay.'),
]
ALL_SETTINGS=SETTINGS+EXTRA_SETTINGS

STATE_FILE=BRIDGE_ROOT/'overlay_state.txt'
COMMAND_FILE=BRIDGE_ROOT/'overlay_command.txt'
# v1.24.10: the overlay writes one uniquely named file per command (atomic rename),
# so commands issued within one 200 ms poll can no longer overwrite each other.
COMMAND_GLOB='overlay_cmd_*.txt'
# Set when a view-only command was applied while FC27 is advancing; the exporter then
# republishes the last reconciled world (without promoting the lifecycle to READY).
_advance_view_dirty=False
# v1.24.13: every processed overlay command changes the published file. The bridge
# reuses a generation when the rebuilt payload is identical, so re-opening the same
# player produced a byte-identical overlay_state.txt; the overlay skips identical
# files and stayed on "Loading player details" until the career data next changed.
# The token is added after the generation hash, so it never creates extra generations.
_COMMAND_EPOCH=int(time.time())
_command_seq=0
VIEW_FILE=BRIDGE_ROOT/'overlay_view.json'
# v1.24.29: player list / events load 100 rows at a time, up to 1000.
PAGE_SIZE=100
PAGE_LIMIT_MAX=1000

DEFAULT_VIEW={
    'storage_key':'','query':'','myclub':True,'position':'All positions','state':'All Development Statuses',
    'playstyle':'Any PlayStyle','role':'Any role','plus_filter':'Any PlayStyle+ Status','ovr_min':0,'ovr_max':0,'pot_min':0,'pot_max':0,
    'age_min':0,'age_max':0,'ps_min':0,'limit':100,'sort_column':0,'ascending':True,'selected_pid':0,
    'ovr_ranges':'Any OVR','pot_ranges':'Any POT',
    'event_limit':100,'event_filter':'All','history_path':'',
    'face_picker':0,'face_region':'','face_limit':0,'face_page_size':24,
}

def _clean(v):
    return str(v if v is not None else '').replace('|','/').replace('\r',' ').replace('\n',' ').strip()

def _runtime_career_state():
    if not detect_game():
        return False,'NO_GAME',{}
    mgr=load_manager_settings(); le=live_editor_status(mgr.get('live_editor_root') or None)
    d=dict(le.get('runtime_marker') or {}); state=str(d.get('state') or '').upper()
    if state in {'DETACHED','NO_CAREER','LEFT_CAREER'}: return False,state,d
    if state in {'ACTIVE','ACTIVE_SETTLING','CAREER_SETTLING'}: return True,state,d
    if le.get('runtime'): return True,state or 'ACTIVE',d
    p=BRIDGE_ROOT/'career_session_status.json'
    try:
        cs=json.loads(p.read_text(encoding='utf-8')); cstate=str(cs.get('state') or '').upper()
        if cstate in {'DETACHED','NO_CAREER','LEFT_CAREER'}: return False,cstate,cs
        if cstate in {'ACTIVE','ACTIVE_SETTLING','CAREER_SETTLING','LOADED','CAREER_LOADED'}: return True,cstate,cs
    except Exception: pass
    return False,state,d

def _same_date(a,b):
    try:return all(int((a or {}).get(k))==int((b or {}).get(k)) for k in ('day','month','year'))
    except Exception:return False

def _bridge_session_status():
    try:return json.loads((BRIDGE_ROOT/'career_session_status.json').read_text(encoding='utf-8'))
    except Exception:return {}

def _career_is_live():
    # A resident Live Editor script can outlive save-selection screens. A fully ACTIVE
    # runtime is immediately usable; while the runtime is synchronising, unlock only
    # after the Python bridge has completed the exact request/date advertised by Lua.
    if not detect_game(): return False
    detected,state,info=_runtime_career_state()
    if not detected:return False
    ctx=active_context(); key=str(ctx.get('storage_key') or ''); world=active_world() or {}
    if not key or not world:return False
    runtime_uid=str((info or {}).get('save_uid') or '').strip(); context_uid=str(ctx.get('career_uid') or '').strip()
    if runtime_uid in {'','DEFERRED','UNKNOWN','NONE'}:return False
    if context_uid and runtime_uid!=context_uid:return False
    st=str(state or '').upper()
    if st=='ACTIVE':return True
    if st not in {'ACTIVE_SETTLING','CAREER_SETTLING'}:return False
    cs=_bridge_session_status()
    if str(cs.get('state') or '').upper()!='ACTIVE':return False
    if str(cs.get('save_uid') or '')!=runtime_uid:return False
    if str(cs.get('storage_key') or '')!=key:return False
    rid=str((info or {}).get('request_id') or '')
    if rid and str(cs.get('request_id') or '')!=rid:return False
    rdate=(info or {}).get('career_date') or {}; cdate=cs.get('career_date') or {}; wdate=(world.get('career') or {}).get('date') or {}
    if rdate and (not _same_date(rdate,cdate) or not _same_date(rdate,wdate)):return False
    return bool(rid or _same_date(cdate,wdate))

def _setting_value(storage_key,spec):
    s=AcademySettings(path=career_settings_path(storage_key))
    return s.data.get(spec['section'],{}).get(spec['key'],spec.get('default'))

def _write_atomic(path:Path,text:str):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(text,encoding='utf-8'); replace_retry(tmp,path)

def _load_view(storage_key:str=''):
    d=dict(DEFAULT_VIEW)
    try:
        raw=json.loads(VIEW_FILE.read_text(encoding='utf-8'))
        if isinstance(raw,dict): d.update(raw)
    except Exception: pass
    if storage_key and d.get('storage_key')!=storage_key:
        d=dict(DEFAULT_VIEW); d['storage_key']=storage_key; _save_view(d)
    if str(d.get('state') or '') == 'PS+ eligible':
        d['state']='All Development Statuses'; d['plus_filter']='Eligible'; _save_view(d)
    if str(d.get('state') or '') in {'All states','All States'}: d['state']='All Development Statuses'
    # v1.24.20 wording: spelled-out PlayStyle labels (older saved views are migrated).
    _plus_map={'Any PS+':'Any PlayStyle+ Status','Any PS +':'Any PlayStyle+ Status','Any PS+ Status':'Any PlayStyle+ Status','Eligible':'PlayStyle+ eligible','Not eligible':'Not PlayStyle+ eligible'}
    if str(d.get('plus_filter') or '') in _plus_map: d['plus_filter']=_plus_map[str(d.get('plus_filter'))]
    if str(d.get('state') or '')=='At lifetime cap': d['state']='At lifetime PlayStyle cap'
    # Column layout migrations for a saved sort column. v1.24.25 inserted NEXT ROLE at 13;
    # v1.24.27 removed STATUS (15), leaving 15 columns ending with ROLE++ PROGRESS (14).
    if int(d.get('layout') or 0)<2:
        try: sc=int(d.get('sort_column') or 0)
        except Exception: sc=0
        if 'columns' not in d and sc>=13: sc+=1
        if sc>=15: sc=0
        d['sort_column']=sc; d['layout']=2; d.pop('columns',None); _save_view(d)
    return d

def _save_view(d):
    try:_write_atomic(VIEW_FILE,json.dumps(d,ensure_ascii=False,separators=(',',':')))
    except Exception:pass

def _sync_read_model_if_needed(storage_key:str, world:dict):
    """Synchronise the immutable UI cache or fail explicitly.

    v1.24.09 swallowed read-model rebuild failures, which could leave lifecycle
    permanently RECONCILING while the overlay showed LOADING CAREER DATA forever.
    The resident bridge now survives exceptions, so publication failures must be
    surfaced as ERROR rather than hidden.
    """
    try:
        if (not read_model.career_meta(storage_key)) or read_model.is_stale(storage_key):
            rows=player_rows(world)
            career=world.get('career') or {}; date=career.get('date') or {}
            date_text=''
            try: date_text=f"{int(date.get('day')):02d}/{int(date.get('month')):02d}/{int(date.get('year')):04d}"
            except Exception: pass
            read_model.sync_world(storage_key,world,rows,date_text)
        if (not read_model.career_meta(storage_key)) or read_model.is_stale(storage_key):
            raise RuntimeError('read model remained stale after synchronization')
        return True
    except Exception as exc:
        raise RuntimeError(f'read-model synchronization failed: {exc}') from exc

def _next_role(r):
    """Highest-progress Role++ path among the player's current Role+ roles (v1.24.25).

    The full ledger (role_progress) also holds roles already upgraded or no longer held."""
    roles=r.get('active_role_progress')
    if roles is None: roles=r.get('role_progress') or {}
    best=('',0.0)
    for k,v in (roles or {}).items():
        try: fv=float(v or 0)
        except Exception: fv=0.0
        if fv>best[1]: best=(str(k),fv)
    return best

def _club_text(r):
    club=str(r.get('club') or '')
    if str(r.get('lifecycle') or '')=='FREE_AGENT' or club.strip().lower().startswith('free agent'): return ''
    return club

def _row_line(r):
    role,rp=_next_role(r)
    nt=float(r.get('normal_threshold') or 100.0); pt=float(r.get('plus_threshold') or 180.0)
    pspct=float(r.get('next_ps_pct') or 0.0); pluspct=float(r.get('next_plus_pct') or 0.0)
    if pspct <= 0 and float(r.get('next_ps_value') or 0) > 0 and nt > 0:
        pspct=min(100.0,100.0*float(r.get('next_ps_value') or 0)/nt)
    if pluspct <= 0 and float(r.get('next_plus_value') or 0) > 0 and pt > 0:
        pluspct=min(100.0,100.0*float(r.get('next_plus_value') or 0)/pt)
    return '|'.join(map(_clean,[
        r.get('playerid'),r.get('name'),r.get('position'),_club_text(r),r.get('age'),r.get('ovr'),r.get('potential'),
        len(r.get('normal_styles') or []),(r.get('cap') if r.get('cap') is not None else 7),r.get('next_ps'),f"{pspct:.1f}",
        r.get('next_plus'),f"{pluspct:.1f}",role,f"{min(100,float(rp or 0)):.1f}",
        r.get('status') or r.get('next_ps_status'),','.join(r.get('normal_styles') or []),','.join(r.get('plus_styles') or []),
        1 if r.get('plus_eligible') else 0,1 if r.get('is_user_team') else 0,', '.join(r.get('roles') or []),
        r.get('next_ps_status_detail') or '',r.get('normal_threshold') or 100,r.get('plus_threshold') or 180,
        r.get('normal_cooldown') or 0,r.get('plus_cooldown') or 0,r.get('role_cooldown') or 0,r.get('lifecycle') or '',
        r.get('next_ps_value') or 0,r.get('next_plus_value') or 0,r.get('dob_text') or '',r.get('nationality_label') or '',
        r.get('clubteamid') or '',r.get('leagueid') or '',1 if r.get('observed_this_checkpoint') else 0,
        r.get('development_checkpoint_count') or 0,
    ]))

def _filter_lists():
    ps=sorted(set(PLAYSTYLE1)|set(PLAYSTYLE2_GK))
    roles=sorted({v for k,v in ROLE_ID_TO_LABEL.items() if k and v and v!='None'})
    return ps,roles

def _event_category(e:dict)->str:
    typ=str((e or {}).get('type') or '').upper().strip()
    if typ in ('PLAYSTYLE_PLUS_GAINED','PLAYSTYLE_PLUS_DOWNGRADED'): return 'PLUS'
    if typ=='ROLE_UPGRADED': return 'ROLE'
    if typ in ('PLAYSTYLE_GAINED','PLAYSTYLE_LOST'): return 'PS'
    return ''

def _event_date(e:dict)->tuple[str,int]:
    raw=(e or {}).get('career_date') or {}
    if isinstance(raw,dict):
        try:
            day=int(raw.get('day') or 0); month=int(raw.get('month') or 0); year=int(raw.get('year') or 0)
            if day and month and year:return f'{day:02d}/{month:02d}/{year:04d}',year*10000+month*100+day
        except Exception:pass
    created=(e or {}).get('created_at') or 0
    try:
        import datetime as _dt
        ts=int(created or 0)
        if ts:return _dt.datetime.fromtimestamp(ts).strftime('%d/%m/%Y'),ts
    except Exception:pass
    return '',0

def _split_names(value:str)->list[str]:
    out=[]
    for part in str(value or '').replace(',', ' + ').split(' + '):
        part=part.strip()
        if part: out.append(part)
    return out

def _acquired_by_engine(detail:dict, kind:str, name:str)->bool:
    """v1.24.27: True when Academy Engine itself gave the player this owned path, so a
    development history exists. FC27-given ones (native, or a Role++ FC27 upgraded) have none."""
    how,_=_acquisition(detail,kind,name)
    return 'by Academy Engine' in how and 'by FC27' not in how

def _acquisition(detail:dict, kind:str, name:str)->tuple[str,str]:
    """v1.24.19: how an owned PlayStyle / PlayStyle+ / Role++ was obtained, from the
    player's recorded events. Returns (description, career date text)."""
    want=str(name or '').strip().lower()
    types={'NORMAL':('PLAYSTYLE_GAINED',),'PLUS':('PLAYSTYLE_PLUS_GAINED',),'ROLE':('ROLE_UPGRADED',)}.get(kind,())
    for e in reversed(list(detail.get('_acq_events') if detail.get('_acq_events') is not None else (detail.get('events') or []))):
        if not isinstance(e,dict) or str(e.get('type') or '') not in types: continue
        names=[n.lower() for n in _split_names(e.get('value'))]
        if kind=='ROLE':
            hit=any(want and (want==n or want in n) for n in names)
        else:
            hit=want in names
        if not hit: continue
        date_text,_=_event_date(e)
        title=str(e.get('title') or '')
        if kind=='NORMAL' and title.startswith('Starting PlayStyles'):
            return ('Starting PlayStyle assigned by Academy Engine when the player was first tracked (new generation or promotion to a club squad)', date_text)
        if kind=='PLUS':
            return ('Developed by Academy Engine (lifetime PlayStyle+)', date_text)
        if kind=='ROLE':
            if str(e.get('source') or '').upper()=='FC27': return ('Upgraded to Role++ by FC27 during the career', date_text)
            return ('Upgraded to Role++ by Academy Engine', date_text)
        return ('Developed by Academy Engine', date_text)
    if kind=='ROLE':
        return ('Role++ the player already had in FC27 when Academy Engine began tracking him', '')
    return ('Already owned in FC27 when Academy Engine began tracking this player', '')

def _acquired_text(detail:dict, kind:str, name:str)->tuple[str,str]:
    how,date_text=_acquisition(detail,kind,name)
    return (f'Acquired{(" on "+date_text) if date_text else ""}. {how}.', date_text)

def _normalize_event(e:dict, storage_key:str='')->dict:
    if not isinstance(e,dict): return {}
    cat=_event_category(e)
    if not cat:return {}
    try: pid=int(e.get('playerid') or 0)
    except Exception: pid=0
    name=str(e.get('player_name') or '')
    if not name and storage_key and pid:
        try:name=str((read_model.get_player(storage_key,pid) or {}).get('name') or '')
        except Exception:pass
    if not name:name=f'Player #{pid}' if pid else 'Player'
    value=str(e.get('value') or '')
    title=str(e.get('title') or {'PS':'PlayStyle Acquired','PLUS':'PlayStyle+ Acquired','ROLE':'Role++ Acquired'}[cat])
    # v1.24.25: consistent capitalised titles, including events recorded by older builds.
    title={'playstyle acquired':'PlayStyle Acquired','playstyle+ acquired':'PlayStyle+ Acquired','role upgraded':'Role++ Acquired','role++ acquired':'Role++ Acquired'}.get(title.strip().lower(),title)
    date_text,date_order=_event_date(e)
    try:created=int(e.get('created_at') or 0)
    except Exception:created=0
    return {'source':e,'category':cat,'type':str(e.get('type') or ''),'playerid':pid,'name':name,'value':value,'title':title,
            'date':date_text,'date_order':date_order,'created_at':created,'event_id':str(e.get('event_id') or ''),
            'is_user_team':bool(e.get('is_user_team'))}

def _merged_normalized_events(storage_key:str, world:dict|None=None)->list[dict]:
    try: rows=events_for_storage(storage_key, mark_read=False)
    except Exception: rows=[]
    result=[]; seen=set()
    # v1.24.36: retired players are hidden everywhere, their events included.
    retired={int(k) for k,p in ((world or {}).get('players') or {}).items() if str(k).isdigit() and p.get('retired')}
    for ev in rows:
        ne=_normalize_event(ev,storage_key)
        if not ne:continue
        if ne.get('playerid') in retired:continue
        key=ne.get('event_id') or (ne['type'],ne['playerid'],ne['value'],ne['date'],ne['created_at'])
        if key in seen:continue
        seen.add(key);result.append(ne)
    result.sort(key=lambda x:(int(x.get('date_order') or 0),int(x.get('created_at') or 0),str(x.get('event_id') or '')),reverse=True)
    return result

def _friendly_runtime_detail(info:dict, *, loading:bool=False)->str:
    raw=str((info or {}).get('detail') or '').strip()
    low=raw.lower()
    if not raw or 'careermodeevent:' in low or low.startswith('event=') or 'resident_ready_no_db_touch' in low:
        return 'Synchronizing the loaded Career Mode save with Academy Engine.' if loading else ''
    if 'screen' in low and 'loaded' in low:return 'Career Mode finished loading. Synchronizing player development data.'
    if 'advanc' in low:return 'FC27 is advancing the career. Academy Engine is waiting for the updated player data.'
    return raw

_last_publication_revision=None
_publication_deadline=float('inf')

def publish_overlay_state(activity:dict|None=None,runtime_override:dict|None=None):
    global _last_publication_revision
    from .overlay_revision import revision
    rev=(revision(tx_lifecycle(),int(game_pid() or 0),activity,runtime_override),_command_seq)
    if STATE_FILE.exists() and rev==_last_publication_revision and time.time()<_publication_deadline:return False
    _publish_overlay_state(activity,runtime_override)
    # Remember only successful publications. If input files changed while building,
    # their new revision will force another pass instead of masking the change.
    _last_publication_revision=rev
    return True

def _publish_overlay_state(activity:dict|None=None,runtime_override:dict|None=None):
    global _publication_deadline
    _publication_deadline=float('inf')
    mgr=load_manager_settings(); theme=str(mgr.get('ui_theme','dark')); t=tokens(theme); game_running=bool(detect_game()); pid=int(game_pid() or 0)
    life=tx_lifecycle(); lstate=str(life.get('state') or ('NO_GAME' if not game_running else 'DETACHED')).upper()
    runtime_info=dict((runtime_override or {}).get('runtime_info') or {})
    # v1.24 publication is lifecycle-driven.  A career UID existing somewhere on disk
    # is not enough: only an atomically completed READY generation is navigable.
    ctl_on,ctl_combo,ctl_mask=controller_settings(mgr)
    lines=['VERSION=1.0.6',f'GAME_PID={pid}',f'GAME_RUNNING={1 if game_running else 0}',f'THEME={theme}',f'HOTKEY={_clean(mgr.get("overlay_hotkey","F8"))}',f'CONTROLLER_ENABLED={1 if ctl_on else 0}',f'CONTROLLER_COMBO={ctl_mask}',f'CONTROLLER_COMBO_NAME={_clean(ctl_combo)}',f'RUNTIME_STATE={_clean(lstate)}']
    for k in ('bg','panel','panel_alt','border','text','text_strong','muted','accent','ps','plus','role','info','good','warn','bad'):
        lines.append(f'COLOR_{k.upper()}={t[k]}')

    career_detected=bool(game_running and lstate in {'CAREER_LOADING','RECONCILING','ADVANCING','READY','ERROR'})
    # RECONCILING with a resolved storage key is intentionally buildable but not
    # yet interactive. The exporter constructs the complete read generation from
    # that state and promotes it to READY only after the atomic payload exists.
    buildable=bool(game_running and lstate in {'RECONCILING','READY'} and life.get('career_uid') and life.get('storage_key'))
    live=bool(game_running and lstate=='READY' and life.get('career_uid') and life.get('storage_key'))
    # During an advance of the same loaded career keep the last immutable READY
    # generation visible underneath the lightweight activity overlay. Commands
    # are already invalidated because lifecycle generation is zero. This gives
    # the user an immediate dimmed REFRESHING indicator instead of blanking the
    # player/event views and then making new values appear suddenly.
    global _advance_view_dirty
    advancing_view=False
    if lstate=='ADVANCING' and STATE_FILE.exists():
        if not (_advance_view_dirty and life.get('career_uid') and life.get('storage_key')):
            return
        # A filter/selection/settings change made while the previous generation is
        # still browseable: rebuild that same reconciled world with the new view.
        advancing_view=True; _advance_view_dirty=False
        buildable=True
    lines += [f'CAREER_DETECTED={1 if career_detected else 0}',f'CAREER_LOADED={1 if buildable else 0}']
    if not buildable:
        loading=bool(game_running and lstate in {'CAREER_LOADING','RECONCILING','ADVANCING'})
        failed=bool(game_running and lstate=='ERROR')
        if not game_running:
            status='FC27 is not running'; detail='Start FC27 and load a Career Mode save.'
        elif failed:
            status='Academy Engine processing error'; detail=str(life.get('detail') or 'Academy Engine could not finish processing this career snapshot. Advance/reload the career to retry, or check the engine log for details.')
        elif loading:
            status='Career detected - synchronizing Academy Engine data'; detail=str(life.get('detail') or 'Building a complete career generation. Controls will unlock when all player progression and event data is ready.')
        else:
            status='Waiting for Career Mode'; detail='Load a Career Mode save. Previous career data has been detached from the live overlay.'
        lock_title='ACADEMY ENGINE ERROR' if failed else ('LOADING CAREER DATA' if loading else '')
        locked=bool(loading or failed)
        lines += [f'CAREER_UID={_clean(life.get("career_uid") or "")}',f'DATA_LOADING={1 if loading else 0}',f'PROCESSING={1 if loading else 0}',f'INTERACTION_LOCK={1 if locked else 0}',f'LOCK_TITLE={lock_title}',f'LOCK_DETAIL={_clean(detail if locked else "")}',f'STAGE_TITLE={lock_title}',f'STAGE_DETAIL={_clean(detail if locked else "")}',f'STAGE_INDEX=0',f'STAGE_TOTAL=0',f'STATUS={_clean(status)}','SUMMARY_PLAYERS=0','SUMMARY_DEVELOPING=0','SUMMARY_DEVELOPING_PLUS=0','SUMMARY_DEVELOPING_ROLE=0','DASH_SUMMARY_DEVELOPING_PLUS=0','DASH_SUMMARY_DEVELOPING_ROLE=0','SUMMARY_PLUS_ELIGIBLE=0','SUMMARY_AT_CAP=0','DASH_SUMMARY_PLAYERS=0','DASH_SUMMARY_DEVELOPING=0','DASH_SUMMARY_PLUS_ELIGIBLE=0','DASH_SUMMARY_AT_CAP=0','PLAYER_TOTAL=0','PLAYER_LIMIT=0','SELECTED_PID=0','EVENT_TOTAL=0','EVENT_COUNT_ALL=0','EVENT_COUNT_PS=0','EVENT_COUNT_PLUS=0','EVENT_COUNT_ROLE=0','PLAYERS_BEGIN','PLAYERS_END','DETAIL_BEGIN','DETAIL_END','PATHS_BEGIN','PATHS_END','PATH_HISTORY_BEGIN','PATH_HISTORY_END','EVENTS_BEGIN','EVENTS_END','TIMELINE_BEGIN','TIMELINE_END','SETTINGS_BEGIN','SETTINGS_END']
        _write_atomic(STATE_FILE,'\n'.join(lines)+'\n'); return

    ctx=active_context(); key=str(life.get('storage_key') or ''); world=active_world() or {}; c=current_career(world)
    if str(ctx.get('storage_key') or '')!=key or str(ctx.get('career_uid') or '')!=str(life.get('career_uid') or ''):
        # Never combine a newly attached runtime with a stale previous-career context.
        lines += ['DATA_LOADING=1','PROCESSING=1','INTERACTION_LOCK=1','LOCK_TITLE=RECONCILING CAREER DATA','LOCK_DETAIL=Waiting for the active Academy Engine context to match the loaded FC27 save.','PLAYERS_BEGIN','PLAYERS_END','DETAIL_BEGIN','DETAIL_END','PATHS_BEGIN','PATHS_END','PATH_HISTORY_BEGIN','PATH_HISTORY_END','EVENTS_BEGIN','EVENTS_END','SETTINGS_BEGIN','SETTINGS_END']
        _write_atomic(STATE_FILE,'\n'.join(lines)+'\n'); return
    d=c.get('date') or {}; date_text=_clean(f"{d.get('day','--')}/{d.get('month','--')}/{d.get('year','----')}")
    lines += [f'STORAGE_KEY={_clean(key)}',f'CAREER_UID={_clean(c.get("career_uid"))}',f'BRANCH_ID={_clean(c.get("branch_id"))}',f'TEAM={_clean(c.get("team_name") or c.get("club_name") or "Career")}',f'SEASON={_clean(c.get("season") or c.get("season_id") or "Career")}',f'CAREER_DATE={date_text}']
    # Build/refresh the complete player read-model before publishing anything.
    # No partial generation is written to overlay_state.txt.
    _sync_read_model_if_needed(key,world)
    view=_load_view(key)
    a=activity or {}; bridge_processing=str(a.get('state') or '').upper()=='RUNNING'; runtime_loading=False
    # The final complete generation is not published until BridgeService has returned.
    # A stale RUNNING activity marker must not keep the newly committed generation
    # locked after all sections have been hydrated.
    processing=bool(bridge_processing and lstate=='READY'); trigger=str(a.get('trigger') or '')
    friendly={'DAY_PASSED':'Updating player development','DAY_SETTLED':'Updating player development','CAREER_SETTLED_BASELINE':'Loading career data','SAVE_STABILIZED':'Updating career data','PREPARE_FOR_SAVE':'Saving Academy Engine progress'}.get(trigger,'Updating Academy Engine data')
    if runtime_loading and not bridge_processing: friendly='CAREER ADVANCING - UPDATING DATA'
    runtime_detail=_clean(_friendly_runtime_detail(runtime_info,loading=runtime_loading))
    lock_detail=_clean(a.get('stage') or a.get('detail') or runtime_detail or 'Please wait until Academy Engine finishes loading or processing career data.')
    lines += [f'DATA_LOADING={1 if runtime_loading else 0}',f'PROCESSING={1 if processing else 0}',f'INTERACTION_LOCK={1 if processing else 0}',f'LOCK_TITLE={_clean(friendly if processing else "")}',f'LOCK_DETAIL={lock_detail if processing else ""}',f'STAGE_TITLE={_clean(friendly if processing else "")}',f'STAGE_DETAIL={_clean(a.get("stage") or a.get("detail") or runtime_detail)}',f'STAGE_INDEX={int(a.get("stage_index") or 0)}',f'STAGE_TOTAL={int(a.get("stage_total") or 0)}']

    filters={'storage_key':key,'query':view.get('query',''),'myclub':bool(view.get('myclub',True)),'position':view.get('position','All positions'),'state':view.get('state','All Development Statuses'),'playstyle':view.get('playstyle','Any PlayStyle'),'role':view.get('role','Any role'),'plus_filter':view.get('plus_filter','Any PlayStyle+ Status'),'ovr_min':view.get('ovr_min',0),'ovr_max':view.get('ovr_max',0),'pot_min':view.get('pot_min',0),'pot_max':view.get('pot_max',0),'ovr_ranges':view.get('ovr_ranges',''),'pot_ranges':view.get('pot_ranges',''),'age_min':view.get('age_min',0),'age_max':view.get('age_max',0),'ps_min':view.get('ps_min',0)}
    limit=max(40,min(PAGE_LIMIT_MAX,int(view.get('limit') or PAGE_SIZE)))
    try: rows,total=read_model.query_players(filters,int(view.get('sort_column') or 0),bool(view.get('ascending',True)),limit,0)
    except Exception: rows,total=[],0
    sums=read_model.summary(key,filters) or {}; dash=read_model.summary(key) or {}
    lines += [f'SUMMARY_DEVELOPING_PLUS={int(sums.get("developing_plus",0))}',f'SUMMARY_DEVELOPING_ROLE={int(sums.get("developing_role",0))}',f'DASH_SUMMARY_DEVELOPING_PLUS={int(dash.get("developing_plus",0))}',f'DASH_SUMMARY_DEVELOPING_ROLE={int(dash.get("developing_role",0))}']
    lines += [f'SUMMARY_PLAYERS={int(sums.get("players",0))}',f'SUMMARY_DEVELOPING={int(sums.get("developing",0))}',f'SUMMARY_PLUS_ELIGIBLE={int(sums.get("plus_eligible",0))}',f'SUMMARY_AT_CAP={int(sums.get("at_cap",0))}',f'DASH_SUMMARY_PLAYERS={int(dash.get("players",0))}',f'DASH_SUMMARY_DEVELOPING={int(dash.get("developing",0))}',f'DASH_SUMMARY_PLUS_ELIGIBLE={int(dash.get("plus_eligible",0))}',f'DASH_SUMMARY_AT_CAP={int(dash.get("at_cap",0))}',f'PLAYER_TOTAL={int(total)}',f'PLAYER_LIMIT={limit}',f'SORT_COLUMN={int(view.get("sort_column") or 0)}',f'SORT_ASC={1 if view.get("ascending",True) else 0}']
    lines += [f'FILTER_MY={1 if view.get("myclub",True) else 0}',f'FILTER_POSITION={_clean(view.get("position","All positions"))}',f'FILTER_STATE={_clean(view.get("state","All Development Statuses"))}',f'FILTER_PLAYSTYLE={_clean(view.get("playstyle","Any PlayStyle"))}',f'FILTER_ROLE={_clean(view.get("role","Any role"))}',f'FILTER_PLUS={_clean(view.get("plus_filter","Any PlayStyle+ Status"))}',f'FILTER_OVR_MIN={int(view.get("ovr_min") or 0)}',f'FILTER_OVR_MAX={int(view.get("ovr_max") or 0)}',f'FILTER_POT_MIN={int(view.get("pot_min") or 0)}',f'FILTER_POT_MAX={int(view.get("pot_max") or 0)}',f'FILTER_AGE_MIN={int(view.get("age_min") or 0)}',f'FILTER_AGE_MAX={int(view.get("age_max") or 0)}',f'FILTER_PS_MIN={int(view.get("ps_min") or 0)}',f'FILTER_OVR_RANGES={_clean(view.get("ovr_ranges") or "Any OVR")}',f'FILTER_POT_RANGES={_clean(view.get("pot_ranges") or "Any POT")}',f'FILTER_QUERY={_clean(view.get("query") or "")}']
    psopts,ropts=_filter_lists(); lines.append('PS_OPTIONS='+';'.join(_clean(x) for x in psopts)); lines.append('ROLE_OPTIONS='+';'.join(_clean(x) for x in ropts))
    event_filter=str(view.get('event_filter') or 'All').strip()
    event_key=event_filter.upper().replace(' ','')
    if event_key in {'PLAYSTYLES','PLAYSTYLE','PS'}: event_filter='PlayStyles'
    elif event_key in {'PLAYSTYLE+','PLAYSTYLEPLUS','PLUS','PS+'}: event_filter='PlayStyle+'
    elif event_key in {'ROLE++','ROLE','ROLES'}: event_filter='Role++'
    else: event_filter='All'
    event_limit=max(40,min(PAGE_LIMIT_MAX,int(view.get('event_limit') or PAGE_SIZE)))
    lines += [f'EVENT_FILTER={_clean(event_filter)}',f'EVENT_LIMIT={event_limit}']

    lines.append('PLAYERS_BEGIN')
    for r in rows: lines.append(_row_line(r))
    lines.append('PLAYERS_END')

    selected_pid=int(view.get('selected_pid') or 0); detail=None
    if selected_pid:
        try: detail=read_model.get_player(key,selected_pid)
        except Exception: detail=None
        if detail is not None and not detail.get('raw'):
            detail['raw']=((world.get('players') or {}).get(str(selected_pid))) or {}
    lines.append(f'SELECTED_PID={selected_pid if detail else 0}')
    # v1.24.31: gender and the library face for the Player Details header.
    sel_gender=''; sel_face=''; sel_face_source=''; picker_lines=[]; faces_on=0
    if detail:
        raw_sel=((world.get('players') or {}).get(str(selected_pid))) or detail.get('raw') or {}
        g_val=(raw_sel.get('game') or {}).get('gender')
        sel_gender=face_lib.gender_label(g_val) if g_val is not None else ''
        try:
            fs=face_lib.face_settings()
            idx=face_lib.load_library(fs['face_library_path']) if fs.get('face_enabled') and fs.get('face_library_path') else {}
            if idx.get('count'):
                faces_on=1
                choices=face_lib.load_choices(_face_choices_path(key))
                cur=face_lib.effective_face(world,selected_pid,idx,choices)
                if cur and cur.get('file'):
                    bmp=overlay_face_bmp(Path(fs['face_library_path'])/cur['file'],t.get('panel','#081b2d'))
                    sel_face=str(bmp) if bmp else ''
                    pend=str(selected_pid) in choices
                    sel_face_source=('Your choice' if cur.get('source')=='user' else 'Automatic')+(' (saved at the next checkpoint)' if pend else '')
                if int(view.get('face_picker') or 0)==int(selected_pid):
                    picker_lines=_face_picker_lines(world,selected_pid,idx,choices,view,fs['face_library_path'],t.get('panel','#081b2d'))
        except Exception as exc:
            sel_face=''; picker_lines=[f'FACE_PICKER_ERROR={_clean(exc)}']
    try:
        _dsince=int(((((detail or {}).get('raw') or {}).get('engine') or {}).get('decline') or {}).get('active_since_age') or 0) if detail and _decline_enabled(key) and ((((detail.get('raw') or {}).get('engine') or {}).get('decline') or {}).get('active')) else 0
    except Exception: _dsince=0
    lines.append(f'SELECTED_DECLINE_SINCE={_dsince}')
    lines += [f'SELECTED_GENDER={_clean(sel_gender)}',f'SELECTED_FACE={_clean(sel_face)}',f'SELECTED_FACE_SOURCE={_clean(sel_face_source)}',f'FACES_ENABLED={faces_on}']
    if not any(l.startswith('FACE_PICKER_PID=') for l in picker_lines): lines.append('FACE_PICKER_PID=0')
    lines += [l for l in picker_lines if not l.startswith('FACE|')]
    lines.append('FACES_BEGIN'); lines += [l for l in picker_lines if l.startswith('FACE|')]; lines.append('FACES_END')
    lines.append('DETAIL_BEGIN')
    if detail: lines.append(_row_line(detail))
    lines.append('DETAIL_END')
    lines.append('PATHS_BEGIN')
    if detail:
        pid=detail.get('playerid')
        # Acquisition sources come from the live events file (the cached row's events
        # are only refreshed when the world changes).
        try:
            from fc27_academy.event_engine import load_events as _load_events
            detail['_acq_events']=[e for e in _load_events(key) if int(e.get('playerid') or 0)==int(pid or 0)]
        except Exception:
            detail['_acq_events']=None
        nt=float(detail.get('normal_threshold') or 0) or 100.0
        normal_paths=list(detail.get('normal_progress_paths') or [])
        listed={str(p.get('style') or '') for p in normal_paths}
        # v1.24.19: every owned PlayStyle is listed (incl. ones FC27 gave the player that
        # never had an Academy Engine path) and shown as complete.
        for st in (detail.get('normal_styles') or []):
            if str(st) and str(st) not in listed: normal_paths.append({'style':str(st),'value':nt,'pct':100.0,'owned':True})
        normal_paths.sort(key=lambda x:(bool(x.get('owned')),-float(x.get('value') or 0)))
        for p in normal_paths:
            pct=float(p.get('pct') or 0); owned=bool(p.get('owned')); style=str(p.get('style') or '')
            if owned:
                expl,_=_acquired_text(detail,'NORMAL',style); pct=100.0; p=dict(p,value=nt)
            elif pct>=100 and style==str(detail.get('next_ps') or ''): expl=str(detail.get('next_ps_status_detail') or detail.get('next_ps_status') or 'Ready for acquisition checks.')
            elif pct>=100: expl='Readiness reached. Candidate ranking and acquisition rules decide which completed path is awarded first.'
            else:
                meta=detail.get('next_ps_meta') or {}
                if style==str(detail.get('next_ps') or ''):
                    inc=float(meta.get('last_increment') or 0); attrs=meta.get('last_source_attributes') or []
                    if inc>0:
                        src=', '.join(str(x) for x in attrs[:4]) if isinstance(attrs,list) else ''
                        expl=f'Readiness increased by {inc:.1f} at the latest qualifying checkpoint'+(f' from observed FC27 development ({src}).' if src else ' from verified FC27 development evidence.')
                    elif int(detail.get('next_ps_checkpoints_since') or 0)>0:
                        expl='No readiness was added at the latest observed checkpoint. Supporting FC27 attributes did not provide enough qualifying development evidence, and any training-opportunity check did not advance this path.'
                    else:
                        expl='This is the current PlayStyle target. Readiness advances only when genuine FC27 development or a permitted training opportunity supplies qualifying evidence.'
                else: expl='Secondary readiness path. It remains available, but the current target is prioritised by the engine’s candidate ranking and development fit.'
            lines.append('|'.join(map(_clean,['NORMAL',pid,style,f"{float(p.get('value') or 0):.2f}",f"{pct:.1f}",1 if owned else 0,expl,0 if owned and not _acquired_by_engine(detail,'NORMAL',style) else 1])))
        # plus_progress_paths may not exist in older world rows; derive it from raw engine when possible.
        plus_paths=detail.get('plus_progress_paths') or []
        if not plus_paths:
            try:
                raw=detail.get('raw') or {}; eng=raw.get('engine') or {}; pp=eng.get('playstyle_plus_progress') or {}; owned=set(detail.get('plus_styles') or [])
                threshold=float(detail.get('plus_threshold') or 180)
                plus_paths=[{'style':str(k),'value':float(v or 0),'pct':min(100.0,100.0*float(v or 0)/threshold) if threshold else 0,'owned':k in owned} for k,v in pp.items()]
            except Exception: plus_paths=[]
        pt=float(detail.get('plus_threshold') or 0) or 100.0
        plus_paths=list(plus_paths)
        plisted={str(p.get('style') or '') for p in plus_paths}
        for st in (detail.get('plus_styles') or []):
            if str(st) and str(st) not in plisted: plus_paths.append({'style':str(st),'value':pt,'pct':100.0,'owned':True})
        plus_paths.sort(key=lambda x:(bool(x.get('owned')),-float(x.get('value') or 0)))
        for p in plus_paths:
            pct=float(p.get('pct') or 0); owned=bool(p.get('owned'))
            if owned:
                expl,_=_acquired_text(detail,'PLUS',str(p.get('style') or '')); pct=100.0; p=dict(p,value=pt)
                expl+=' Academy Engine allows one PlayStyle+ per player.'
            elif not detail.get('plus_eligible'): expl='Not currently eligible for an Academy Engine PlayStyle+ award.'
            elif pct>=100: expl='PlayStyle+ readiness reached. Award still requires the verified eligibility and production-write checks.'
            else:
                meta=detail.get('next_plus_meta') or detail.get('next_ps_meta') or {}
                inc=float(meta.get('last_increment') or 0)
                expl=(f'Eligible PlayStyle+ path. The latest qualifying checkpoint added {inc:.1f} readiness from verified development evidence.' if inc>0 else 'Eligible PlayStyle+ path. Progress remains evidence-driven; no qualifying readiness increase was recorded at the latest observed checkpoint.')
            lines.append('|'.join(map(_clean,['PLUS',pid,p.get('style'),f"{float(p.get('value') or 0):.2f}",f"{pct:.1f}",1 if owned else 0,expl,0 if owned and not _acquired_by_engine(detail,'PLUS',str(p.get('style') or '')) else 1])))
        for rn,rv in (detail.get('role_progress') or {}).items():
            pct=min(100,float(rv or 0)); owned=any(str(label).split(' ',1)[-1].rstrip('+').strip()==str(rn).strip() and '++' in str(label) for label in (detail.get('roles') or []))
            if owned: pct=100.0
            expl=(_acquired_text(detail,'ROLE',str(rn))[0] if owned else ('Role++ readiness reached; final mapping/cooldown checks still apply.' if pct>=100 else 'Role++ path is waiting for genuine FC27 development evidence that supports this role. Readiness is not advanced simply by time passing.'))
            lines.append('|'.join(map(_clean,['ROLE',pid,rn,f"{float(rv or 0):.2f}",f"{pct:.1f}",1 if owned else 0,expl,0 if owned and not _acquired_by_engine(detail,'ROLE',str(rn)) else 1])))
        # v1.24.36: PlayStyle decline rows (only once the decline phase is active).
        try: lines.extend(_decline_path_lines(detail,key))
        except Exception: pass
    lines.append('PATHS_END')
    lines.append('PATH_HISTORY_BEGIN')
    if detail:
        pid=int(detail.get('playerid') or 0)
        raw=detail.get('raw') or {}; eng=raw.get('engine') or {}
        history_sources=(
            ('NORMAL', eng.get('playstyle_progress_meta') or {}),
            ('PLUS', eng.get('playstyle_plus_progress_meta') or {}),
            ('ROLE', eng.get('role_progress_meta') or {}),
        )
        for kind,meta_map in history_sources:
            if not isinstance(meta_map,dict): continue
            for path_name,meta in meta_map.items():
                if view.get('history_path')!=kind+':'+str(path_name): continue
                from fc27_academy.path_history_store import history
                hist=history(meta or {})
                if not isinstance(hist,list): continue
                for h in hist[-48:]:
                    if not isinstance(h,dict): continue
                    cd=h.get('career_date') or h.get('date') or {}
                    if isinstance(cd,dict) and cd:
                        dt=f"{int(cd.get('day') or 0):02d}/{int(cd.get('month') or 0):02d}/{int(cd.get('year') or 0):04d}"
                    else:
                        dt='Career checkpoint'
                    attrs=h.get('source_attributes') or []
                    if isinstance(attrs,list): attrs=', '.join(str(x) for x in attrs[:6])
                    source=str(h.get('source') or '')
                    detail_text=(f"+{float(h.get('increment') or 0):.2f} readiness" + (f" • {attrs}" if attrs else '') + (f" • {source.replace('_',' ')}" if source else ''))
                    lines.append('|'.join(map(_clean,[kind,pid,path_name,dt,f"{float(h.get('from') or 0):.2f}",f"{float(h.get('to') or 0):.2f}",f"{float(h.get('increment') or 0):.2f}",detail_text])))
        # v1.24.19: an owned path's history ends with how and when it was acquired
        # (e.g. a starting PlayStyle assigned on promotion), shown newest-first.
        hp=str(view.get('history_path') or '')
        if ':' in hp:
            hk,hn=hp.split(':',1)
            if hk=='ROLE':
                owned=any(str(label).split(' ',1)[-1].rstrip('+').strip()==hn.strip() and '++' in str(label) for label in (detail.get('roles') or []))
                thr=100.0
            else:
                owned=hn in {str(x) for x in (detail.get('normal_styles' if hk=='NORMAL' else 'plus_styles') or [])}
                thr=float(detail.get('normal_threshold' if hk=='NORMAL' else 'plus_threshold') or 100.0)
            if owned:
                how,date_text=_acquisition(detail,hk,hn)
                lines.append('|'.join(map(_clean,[hk,pid,hn,date_text or 'Before tracking',f"{thr:.2f}",f"{thr:.2f}","0.00",'ACQUIRED • '+how])))
    lines.append('PATH_HISTORY_END')
    lines.append('TIMELINE_BEGIN')
    if detail:
        pid=int(detail.get('playerid') or 0); timeline_rows=[]; seen=set()
        for ne in _merged_normalized_events(key,world):
            if not ne or ne['playerid']!=pid: continue
            dedupe=(ne['category'],ne['value'],ne['date'])
            if dedupe in seen:continue
            seen.add(dedupe); timeline_rows.append(ne)
        # Durable player history restores milestones even when convenience event history
        # was cleared or older builds did not create an event row.
        for h in (detail.get('history') or []):
            if not isinstance(h,dict):continue
            typ=str(h.get('type') or '').upper(); cat=''; value=''; title=''
            if typ in {'PLAYSTYLE_PRODUCTION_COMMIT','PLAYSTYLE_PLUS_PRODUCTION_COMMIT','PLUS_PRODUCTION_COMMIT','ROLE_PRODUCTION_COMMIT'} and not (h.get('career_date') or h.get('date') or h.get('created_at')):
                continue
            if typ=='PLAYSTYLE_PRODUCTION_COMMIT':
                if str(h.get('kind') or '').upper()=='PLUS_ACQUISITION': cat='PLUS'; value=str(h.get('style') or 'PlayStyle+'); title='PlayStyle+ Acquired'
                elif str(h.get('kind') or '').upper()=='NEWGEN_ENRICHMENT': cat='PS';value=str(h.get('style') or 'PlayStyles');title='Starting PlayStyles assigned'
                else: cat='PS';value=str(h.get('style') or 'PlayStyle');title='PlayStyle Acquired'
            elif typ in {'PLAYSTYLE_PLUS_PRODUCTION_COMMIT','PLUS_PRODUCTION_COMMIT'}:cat='PLUS';value=str(h.get('style') or 'PlayStyle+');title='PlayStyle+ Acquired'
            elif typ=='ROLE_PRODUCTION_COMMIT':cat='ROLE';value=str(h.get('role') or 'Role++');title='Role++ Acquired'
            elif typ=='AGE_CHECKPOINT':
                value=f"Age {h.get('age','')}"; title='Career checkpoint'; cat='INFO'
            elif typ=='LIFECYCLE_TRANSITION':
                value=f"{h.get('from','')} -> {h.get('to','')}"; title='Lifecycle transition'; cat='INFO'
            else:continue
            dt,ordv=_event_date({'career_date':h.get('career_date') or h.get('date') or {},'created_at':h.get('created_at') or 0})
            dedupe=(cat,value,dt)
            if dedupe in seen:continue
            seen.add(dedupe); timeline_rows.append({'category':cat,'type':{'PS':'PLAYSTYLE_GAINED','PLUS':'PLAYSTYLE_PLUS_GAINED','ROLE':'ROLE_UPGRADED'}.get(cat,'INFO'),'playerid':pid,'name':detail.get('name') or f'Player #{pid}','value':value,'date':dt,'title':title,'date_order':ordv,'created_at':int(h.get('created_at') or 0)})
        timeline_rows.sort(key=lambda x:(int(x.get('date_order') or 0),int(x.get('created_at') or 0)),reverse=True)
        for ne in timeline_rows[:200]:
            lines.append('|'.join(map(_clean,[pid,ne.get('type'),ne.get('name') or detail.get('name'),ne.get('value'),ne.get('date'),ne.get('title'),0])))
    lines.append('TIMELINE_END')

    cfg=AcademySettings(path=career_settings_path(key)).data; notif=cfg.get('notifications') or {}
    normalized=_merged_normalized_events(key,world)
    toast_candidates=[e for e in normalized if int(e.get('created_at') or 0)>0]
    toast_event=max(toast_candidates,key=lambda e:int(e.get('created_at') or 0)) if toast_candidates else None
    toast_notify=False; toast_sig=''; toast_text=''
    if toast_event:
        typ=toast_event['type']; toast_notify=bool(notif.get('overlay_enabled',True))
        if typ=='PLAYSTYLE_GAINED': toast_notify &= bool(notif.get('playstyle_gained',True))
        if typ=='PLAYSTYLE_PLUS_GAINED': toast_notify &= bool(notif.get('playstyle_plus_gained',True))
        if typ=='ROLE_UPGRADED': toast_notify &= bool(notif.get('role_upgraded',True))
        if typ in ('PLAYSTYLE_LOST','PLAYSTYLE_PLUS_DOWNGRADED'): toast_notify &= bool(notif.get('playstyle_lost',True))
        if notif.get('only_user_team',True):
            explicit=toast_event.get('is_user_team')
            if explicit is not None:
                toast_notify &= bool(explicit)
            else:
                try: er=read_model.get_player(key,int(toast_event.get('playerid') or 0)) or {}; toast_notify &= bool(er.get('is_user_team',False))
                except Exception: toast_notify=False
        toast_sig='|'.join(map(_clean,[toast_event.get('event_id') or '',typ,toast_event.get('playerid'),toast_event.get('value')]))
        toast_text=f"{toast_event.get('name')} — {toast_event.get('value') or toast_event.get('title')}"
    popup_seconds=int(notif.get('popup_seconds',6) or 6)
    fresh=False
    if toast_event and int(toast_event.get('created_at') or 0):
        expires=int(toast_event.get('created_at') or 0)+max(60,popup_seconds+20)
        fresh=time.time()<=expires
        if fresh:_publication_deadline=expires
    lines += [f'TOAST_EVENT_SIG={_clean(toast_sig)}',f'TOAST_EVENT_TEXT={_clean(toast_text)}',f'TOAST_EVENT_NOTIFY={1 if toast_notify else 0}',f'TOAST_EVENT_FRESH={1 if fresh else 0}',f'TOAST_DURATION_TICKS={max(300,min(2000,popup_seconds*100))}']
    event_ps=sum(1 for e in normalized if e['category']=='PS'); event_plus=sum(1 for e in normalized if e['category']=='PLUS'); event_role=sum(1 for e in normalized if e['category']=='ROLE')
    filtered=[]
    for ne in normalized:
        if event_filter=='PlayStyles' and ne['category']!='PS':continue
        if event_filter=='PlayStyle+' and ne['category']!='PLUS':continue
        if event_filter=='Role++' and ne['category']!='ROLE':continue
        filtered.append(ne)
    lines += [f'EVENT_TOTAL={len(filtered)}',f'EVENT_COUNT_ALL={len(normalized)}',f'EVENT_COUNT_PS={event_ps}',f'EVENT_COUNT_PLUS={event_plus}',f'EVENT_COUNT_ROLE={event_role}']
    lines.append('EVENTS_BEGIN')
    for ne in filtered[:event_limit]:
        typ=ne['type']; toast_ok=bool(notif.get('overlay_enabled',True))
        if typ=='PLAYSTYLE_GAINED': toast_ok &= bool(notif.get('playstyle_gained',True))
        if typ=='PLAYSTYLE_PLUS_GAINED': toast_ok &= bool(notif.get('playstyle_plus_gained',True))
        if typ=='ROLE_UPGRADED': toast_ok &= bool(notif.get('role_upgraded',True))
        if notif.get('only_user_team',True):
            explicit=ne.get('is_user_team')
            if explicit is not None:
                toast_ok &= bool(explicit)
            else:
                try: er=read_model.get_player(key,int(ne.get('playerid') or 0)) or {}; toast_ok &= bool(er.get('is_user_team',False))
                except Exception: toast_ok=False
        lines.append('|'.join(map(_clean,[ne.get('playerid'),typ,ne.get('name'),ne.get('value'),ne.get('date'),ne.get('title'),1 if toast_ok else 0])))
    lines.append('EVENTS_END')

    lines.append('SETTINGS_BEGIN')
    group_meta={gid:(title,desc) for gid,title,desc in SETTINGS_GROUPS}
    group_meta['notifications']=('Overlay notifications','Controls which play-time notifications appear while the main Academy Engine browser is hidden or open.')
    group_meta['appearance']=('Misc','Theme, hotkey and controller options for the in-game Academy Engine interface.')
    group_meta['maintenance']=('Maintenance','Safe local maintenance controls for the currently loaded career and Academy Engine diagnostics.')
    group_meta['faces']=('Player faces','Faces for generated players from your own regen-face library. The library folder is chosen in the launcher; images are only read, never copied or changed.')
    group_meta['safety']=('Protected safety rules','Hard engine limits that remain fixed to preserve progression integrity and verified FC27 write behavior.')
    # v1.24.20: debug / stress-test settings sit at the bottom of the page.
    group_order=[x[0] for x in SETTINGS_GROUPS if x[0]!='debug']+(['faces'] if face_lib.faces_visible() else [])+['notifications','maintenance','appearance']+(['debug'] if debug_mode_available() else [])
    # v1.24.38: with debug mode hidden, a career that still has it on goes back to normal ranges.
    if not debug_mode_available(): _retire_hidden_debug(key)
    # v1.24.29: protected values are listed at the top of the page instead of their own section.
    lines.append('PROTECTED_RULES='+_clean('   •   '.join(f'{t}: {v} ({d.rstrip(".")})' for t,v,d in LOCKED_INFO)))
    debug_enabled=debug_mode_available() and bool(_setting_value(key,next(x for x in ALL_SETTINGS if x.get('key')=='debug_stress_mode')))
    for gid in group_order:
        title,desc=group_meta[gid]; lines.append('|'.join(map(_clean,['GROUP',gid,str(title).upper(),desc])))
        for s in [x for x in ALL_SETTINGS if x.get('ui_group')==gid]:
            val=_setting_value(key,s); mx=s.get('maximum','')
            if debug_enabled and s.get('key') in {'max_total_changes_per_checkpoint','max_normal_playstyles_per_checkpoint','max_playstyle_plus_per_checkpoint','max_role_transactions_per_checkpoint'}: mx=512
            if debug_enabled and s.get('key')=='newgen_enrichment_per_checkpoint': mx=500
            mn=s.get('minimum','')
            # v1.24.29: debug / stress-test mode widens development speeds and progress targets.
            if debug_enabled and s.get('key') in DEBUG_SPEED_KEYS: mx=DEBUG_SPEED_MAX
            if debug_enabled and s.get('key') in DEBUG_TARGET_MIN: mn=DEBUG_TARGET_MIN[s['key']]
            default_val=s.get('default',''); rec_val=s.get('recommended','')
            if s.get('kind')=='bool':
                default_val='On' if str(default_val).lower() in {'1','true','yes','on'} else 'Off'
                if str(rec_val).lower() in {'1','true','yes','on'}: rec_val='On'
                elif str(rec_val).lower() in {'0','false','no','off'}: rec_val='Off'
            lines.append('|'.join(map(_clean,['SETTING',s['section'],s['key'],s['title'],s['kind'],val,mn,mx,s.get('step',''),s.get('suffix',''),s.get('ui_group',''),default_val,rec_val,s.get('description','')])))
        if gid=='maintenance':
            for key_,title_,desc_ in [
                ('clear_logs','Clear engine logs','Delete local Academy Engine log files. Career progression data is not changed.'),
                ('delete_current_data','Delete current career engine data','Delete Academy Engine persistent data for the career currently loaded in FC27. This is destructive and will require the engine to establish fresh state.')]:
                lines.append('|'.join(map(_clean,['SETTING','maintenance',key_,title_,'action','Run','','','','','maintenance','','Requires confirmation',desc_])))
        if gid=='faces':
            lines.extend(_face_setting_lines(mgr))
        if gid=='appearance':
            lines.append('|'.join(map(_clean,['SETTING','global','ui_theme','UI theme','choice',theme,'','','','','appearance','Dark','','Choose the visual theme used by both the launcher and external overlay.'])))
            lines.append('|'.join(map(_clean,['SETTING','global','overlay_hotkey','Overlay hotkey','hotkey',mgr.get('overlay_hotkey','F8'),'','','','','appearance','F8','','Keyboard shortcut used to show or hide the Academy Engine overlay.'])))
            lines.append('|'.join(map(_clean,['SETTING','global','controller_enabled','Controller support','bool','true' if ctl_on else 'false','','','','','appearance','On','On',controller_help_text(normalize_combo(ctl_combo) or 'L3+R3',True)])))
            lines.append('|'.join(map(_clean,['SETTING','global','controller_combo','Controller open combo','cycle',ctl_combo,'','','','','appearance','L3+R3',';'.join(CONTROLLER_PRESETS),'Button combination that shows or hides the overlay while FC27 or the overlay is focused. Custom combos can be set in the launcher.'])))
    lines.append('SETTINGS_END')
    payload='\n'.join(lines)+'\n'
    gen=0
    try:
        # Journal the complete generation first, but do not mark it READY until
        # the external overlay file itself has been atomically replaced.
        gen=tx_publish_generation(payload,runtime_session=str(life.get('runtime_session') or ''),career_uid=str(life.get('career_uid') or ''),storage_key=key,request_id=str(life.get('request_id') or ''),career_date=life.get('career_date') or (world.get('career') or {}).get('date') or {},promote=False)
        lines.insert(2,f'MODEL_GENERATION={gen}')
        lines.insert(3,f'COMMAND_SEQ={_COMMAND_EPOCH}.{_command_seq}')
    except Exception:
        gen=0
    _write_atomic(STATE_FILE,'\n'.join(lines)+'\n')
    if gen and lstate!='ADVANCING':
        # Promotion is the final commit point. Commands remain blocked until this
        # point, and every visible section now belongs to the same generation.
        tx_set_lifecycle('READY',detail='Career data ready',generation=gen)

DEBUG_SPEED_KEYS={'playstyle_progression_speed','playstyle_plus_progression_speed','role_progression_speed','decline_speed'}
DEBUG_SPEED_MAX=100.0
DEBUG_TARGET_MIN={'normal_playstyle_threshold':10.0,'playstyle_plus_threshold':10.0}
NORMAL_RANGE_CLAMPS={'decline_speed':(0.10,10.0),'playstyle_progression_speed':(0.10,10.0),'playstyle_plus_progression_speed':(0.10,10.0),'role_progression_speed':(0.10,10.0),
                     'normal_playstyle_threshold':(50.0,200.0),'playstyle_plus_threshold':(100.0,360.0)}

NORMAL_NON_DEBUG_LIMITS={
    'max_total_changes_per_checkpoint':64,
    'max_normal_playstyles_per_checkpoint':64,
    'max_playstyle_plus_per_checkpoint':64,
    'max_role_transactions_per_checkpoint':64,
    'newgen_enrichment_per_checkpoint':50,
}

def _clamp_to_normal_ranges(data:dict)->bool:
    """Bring debug-only values back inside the normal ranges (in place)."""
    prod=data.setdefault('production',{}); changed=False
    for key,cap in NORMAL_NON_DEBUG_LIMITS.items():
        try:cur=float(prod.get(key,cap))
        except Exception:cur=float(cap)
        if cur>cap: prod[key]=int(cap);changed=True
    # v1.24.29: speeds/targets widened by debug mode return to their normal ranges.
    for key,(lo,hi) in NORMAL_RANGE_CLAMPS.items():
        d=data.setdefault('decline' if key=='decline_speed' else ('development' if 'speed' in key else 'production'),{})
        if key not in d: continue
        try:cur=float(d.get(key))
        except Exception:continue
        nv=min(hi,max(lo,cur))
        if nv!=cur: d[key]=nv;changed=True
    try:
        if float(prod.get('playstyle_plus_threshold',180))<float(prod.get('normal_playstyle_threshold',100)):
            prod['playstyle_plus_threshold']=float(prod.get('normal_playstyle_threshold',100));changed=True
    except Exception: pass
    return changed

def _retire_hidden_debug(storage_key:str)->bool:
    """Debug mode is hidden (v1.24.38): switch it off in this career and clamp its values."""
    if not storage_key:return False
    try:
        cfg=AcademySettings(path=career_settings_path(storage_key))
        if not bool((cfg.data.get('production') or {}).get('debug_stress_mode',False)):return False
        _clamp_to_normal_ranges(cfg.data); cfg.data.setdefault('production',{})['debug_stress_mode']=False
        cfg.save()
        return True
    except Exception:return False

def _enforce_non_debug_limits(storage_key:str)->bool:
    if not storage_key:return False
    try:
        cfg=AcademySettings(path=career_settings_path(storage_key))
        if bool(cfg.data.setdefault('production',{}).get('debug_stress_mode',False)):return False
        changed=_clamp_to_normal_ranges(cfg.data)
        if changed:cfg.save()
        return changed
    except Exception:return False

_ATTR_LABELS={'sprintspeed':'Sprint speed','acceleration':'Acceleration','agility':'Agility','balance':'Balance','stamina':'Stamina','strength':'Strength',
              'jumping':'Jumping','reactions':'Reactions','shotpower':'Shot power','longshots':'Long shots','finishing':'Finishing','volleys':'Volleys',
              'headingaccuracy':'Heading accuracy','defensiveawareness':'Defensive awareness','standingtackle':'Standing tackle','slidingtackle':'Sliding tackle',
              'interceptions':'Interceptions','aggression':'Aggression','composure':'Composure','ballcontrol':'Ball control','dribbling':'Dribbling','curve':'Curve',
              'freekickaccuracy':'Free kick accuracy','shortpassing':'Short passing','longpassing':'Long passing','vision':'Vision','crossing':'Crossing','positioning':'Positioning',
              'gkdiving':'GK diving','gkhandling':'GK handling','gkkicking':'GK kicking','gkpositioning':'GK positioning','gkreflexes':'GK reflexes'}

def _decline_enabled(storage_key:str)->bool:
    d=(AcademySettings(path=career_settings_path(storage_key)).data.get('decline') or {})
    return bool(d.get('playstyle_loss_enabled') or d.get('playstyle_plus_loss_enabled'))

def _decline_path_lines(detail:dict,storage_key:str)->list[str]:
    """DECLINE rows for the Development page: status codes 0 declining, 1 recovering,
    2 loss pending, 3 lost, 4 holding."""
    from fc27_academy.playstyle_decline import FLOOR
    raw=detail.get('raw') or {}; d=((raw.get('engine') or {}).get('decline') or {})
    if not d.get('active') or not _decline_enabled(storage_key): return []
    pid=int(detail.get('playerid') or 0); prog=d.get('progress') or {}; ready=d.get('ready') or {}
    rows=[]
    for s,st in (d.get('status') or {}).items():
        v=float(prog.get(s,0) or 0); name=f'{s}+' if st.get('plus') else s
        parts=[]
        for a in st.get('attrs') or []:
            cur=(st.get('values') or {}).get(a); pk=(st.get('peaks') or {}).get(a)
            lab=_ATTR_LABELS.get(a,a)
            parts.append(f'{lab} {cur} (peak {pk})' if cur is not None and pk is not None and cur!=pk else f'{lab} {cur}')
        attrs_txt=', '.join(parts)
        if ready.get('style')==s:
            code=2; desc=(f'Ready to drop to {s}. ' if st.get('plus') else 'Ready to be lost. ')+'It is written to FC27 at the next available write.'
        elif v>=100:
            code=2; desc=f'{attrs_txt}: decline complete. It is lost once 60 days have passed since his previous loss.'
        elif st.get('declining'):
            code=0; desc=f'{attrs_txt}: below {FLOOR:.0f} and well below his peak, so decline is building.'
        elif v>0:
            code=1; desc=f'{attrs_txt}: back above the decline line, so progress is easing back.'
        else:
            code=4; desc=f'{attrs_txt}: holding. Decline builds only below {FLOOR:.0f} and well below his peak.'
        order={2:0,0:1,1:2,4:3}[code]
        rows.append((order,-v,name,['DECLINE',pid,name,f'{v:.2f}',f'{min(100.0,v):.1f}',code,desc,0]))
    for i,x in enumerate(reversed(d.get('lost') or [])):
        s=str(x.get('style') or ''); date_text,_=_event_date({'career_date':x.get('career_date') or {}})
        when=f" on {date_text}" if date_text else ''
        if x.get('kind')=='PLUS_DOWNGRADE':
            name=f'{s}+'
            if x.get('kept_normal') is False:
                desc=f'PlayStyle+ removed at age {x.get("age")}{when}. {s} was not kept either.'
            else:
                desc=f'Dropped to {s} at age {x.get("age")}{when}.'
        else:
            name=s; cap=''
            if x.get('cap_before') is not None and x.get('cap_after') is not None and x.get('cap_before')!=x.get('cap_after'):
                cap=f" Lifetime cap {x.get('cap_before')} → {x.get('cap_after')}."
            desc=f'Lost at age {x.get("age")}{when}.{cap}'
        rows.append((9,i,name,['DECLINE',pid,name,'100.00','100.0',3,desc,0]))
    rows.sort(key=lambda r:(r[0],r[1],r[2]))
    return ['|'.join(map(_clean,r[3])) for r in rows]

def _face_choices_path(storage_key:str)->Path:
    from .live_data import STATE_ROOT
    return STATE_ROOT/str(storage_key)/face_lib.CHOICES_NAME

def _face_picker_lines(world:dict,pid:int,idx:dict,choices:dict,view:dict,lib:str,panel:str)->list[str]:
    # v1.24.33: one growing list ("Load more faces") instead of pages; friendly region names.
    from fc27_academy.face_regions import region_label
    batch=face_lib.PICKER_PAGE   # v1.24.35: 50 faces per batch for every region
    try: limit=int(view.get('face_limit') or 0)
    except Exception: limit=0
    pg=face_lib.picker_page(world,pid,idx,str(view.get('face_region') or ''),limit,choices,batch)
    if not pg: return []
    regs=';'.join(f'{r}:{region_label(r)}' for r in pg['regions'])
    out=[f'FACE_PICKER_PID={int(pid)}',f'FACE_PICKER_GENDER={"Women" if pg["gender"]=="F" else "Men"}',
         f'FACE_PICKER_REGION={_clean(pg["region"])}',f'FACE_PICKER_REGION_LABEL={_clean(region_label(pg["region"]))}',
         f'FACE_PICKER_REGIONS={_clean(regs)}',f'FACE_PICKER_SHOWN={pg["shown"]}',f'FACE_PICKER_TOTAL={pg["total"]}',
         f'FACE_PICKER_BATCH={batch}']
    for f in pg['faces']:
        bmp=overlay_face_bmp(Path(lib)/f['file'],panel)
        out.append('|'.join(map(_clean,['FACE',f['file'],str(bmp or ''),1 if f['current'] else 0,1 if f['in_use'] else 0])))
    return out

def _face_setting_lines(mgr:dict)->list[str]:
    on=bool(mgr.get('face_enabled',False)); lib=str(mgr.get('face_library_path') or '').strip()
    if not lib: state,info='Not set','No face library chosen yet. Choose your regen-face folder in the launcher (Settings > Player faces).'
    elif not Path(lib).is_dir(): state,info='Missing',f'Folder not found: {lib}. Choose the folder again in the launcher.'
    else:
        idx=face_lib.load_library(lib)
        state='Ready' if idx.get('count') else 'Empty'
        info=f'{lib}  •  {face_lib.library_summary(idx)}. Men: one folder per region; women: WF\\<region>. Change the folder in the launcher.'
    out=[
        ['SETTING','global','face_enabled','Player faces','bool','true' if on else 'false','','','','','faces','Off','','Give every tracked generated player a face from your library, matched to nationality and gender (with a small chance of mixed heritage). Faces appear in Player Details after the next checkpoint and are saved with the career.'],
        ['SETTING','global','face_library','Face library','info',state,'','','','','faces','','',info],
        ['SETTING','global','face_write_ingame','Write faces into FC27 (experimental)','bool','true' if mgr.get('face_write_ingame') else 'false','','','','','faces','Off','Off','Writes each face as a Live Editor miniface (mods\\legacy\\...\\heads\\p<id>.dds). Live Editor 27.1.x does not yet show minifaces for generated players in-game, so this is off by default. Only files the Academy Engine wrote are ever replaced or removed.'],
    ]
    return ['|'.join(map(_clean,row)) for row in out]

def _apply_setting(scope,section,key,value):
    if scope=='global':
        m=load_manager_settings()
        if key=='ui_theme': m['ui_theme']='light' if value.lower()=='light' else 'dark'
        elif key=='overlay_hotkey' and value.upper() in {f'F{i}' for i in range(1,13)}: m['overlay_hotkey']=value.upper()
        elif key=='controller_enabled': m['controller_enabled']=value.lower() in {'1','true','yes','on'}
        elif key=='controller_combo' and normalize_combo(value): m['controller_combo']=normalize_combo(value)
        elif key in ('face_enabled','face_write_ingame') and face_lib.faces_visible(): m[key]=value.lower() in {'1','true','yes','on'}
        else:return False
        save_manager_settings(m);return True
    ctx=active_context(); storage=str(ctx.get('storage_key') or '')
    if not storage:return False
    spec=next((s for s in ALL_SETTINGS if s['section']==section and s['key']==key),None)
    if not spec:return False
    try:
        if spec['kind']=='bool': parsed=value.lower() in {'1','true','yes','on'}
        elif spec['kind']=='int': parsed=int(float(value))
        else: parsed=float(value)
        if key=='debug_stress_mode' and not debug_mode_available():return False
        cfg=AcademySettings(path=career_settings_path(storage))
        # Normal gameplay limits remain authoritative while stress mode is off.
        debug=debug_mode_available() and bool((cfg.data.get('production') or {}).get('debug_stress_mode',False))
        if key in NORMAL_NON_DEBUG_LIMITS and not debug:parsed=min(parsed,NORMAL_NON_DEBUG_LIMITS[key])
        if key in NORMAL_RANGE_CLAMPS:
            lo,hi=NORMAL_RANGE_CLAMPS[key]
            if debug: lo=DEBUG_TARGET_MIN.get(key,lo); hi=DEBUG_SPEED_MAX if key in DEBUG_SPEED_KEYS else hi
            parsed=min(hi,max(lo,float(parsed)))
        # Turning debug off: clamp debug-only values first so the save validates.
        if section=='production' and key=='debug_stress_mode' and not bool(parsed): _clamp_to_normal_ranges(cfg.data)
        cfg.set(section,key,parsed);cfg.save()
        if section=='production' and key=='debug_stress_mode' and not bool(parsed):_enforce_non_debug_limits(storage)
        return True
    except Exception:return False

_NON_DESTRUCTIVE={'SET','VIEW','SELECT','FACE'}

def _pending_command_files():
    files=sorted(BRIDGE_ROOT.glob(COMMAND_GLOB))
    if COMMAND_FILE.exists(): files.append(COMMAND_FILE)   # legacy single-slot overlay
    return files

def process_overlay_command():
    """Apply queued overlay commands (v1.24.10).

    Commands are bound to the career, not only to the exact READY generation:
    - view/selection/settings commands are accepted when the generation they were
      issued from belongs to the career that is still active, including while FC27
      is advancing (v1.24.09 silently deleted them because generation was 0);
    - destructive actions still require the exact current READY generation;
    - while a snapshot is being reconciled the command waits instead of being lost.
    """
    global _advance_view_dirty, _command_seq
    files=_pending_command_files()
    if not files: return False
    try: life=tx_lifecycle()
    except Exception: life={}
    state=str(life.get('state') or '').upper()
    if state=='RECONCILING':
        now=time.time()
        for f in files:   # keep for the next loop unless clearly stale
            try:
                if now-f.stat().st_mtime>60: f.unlink(missing_ok=True)
            except OSError: pass
        return False
    if state not in {'READY','ADVANCING'}:
        for f in files:
            try: f.unlink(missing_ok=True)
            except OSError: pass
        return False
    changed=False
    for f in files:
        try: raw=f.read_text(encoding='utf-8')
        except Exception: raw=''
        try: f.unlink(missing_ok=True)
        except Exception: pass
        changed=_apply_command_text(raw,life,state) or changed
    if changed:
        _command_seq+=1
    if changed and state=='ADVANCING':
        _advance_view_dirty=True
    return changed

def _apply_command_text(raw,life,state):
    lines_in=[line.strip() for line in (raw or '').splitlines() if line.strip()]
    if not lines_in: return False
    head=lines_in[0].split('|')
    try:
        command_generation=int(head[1]) if len(head)>=2 and head[0].upper()=='GEN' else 0
        current_generation=int(life.get('generation') or 0)
    except Exception:
        command_generation=0; current_generation=0
    if command_generation<=0: return False
    exact=(state=='READY' and command_generation==current_generation)
    same_career=False
    if not exact:
        try: same_career=bool(life.get('storage_key')) and tx_generation_storage_key(command_generation)==str(life.get('storage_key') or '')
        except Exception: same_career=False
    if not (exact or same_career): return False
    changed=False
    for line in lines_in[1:]:
        parts=line.split('|'); cmd=parts[0].upper()
        if cmd not in _NON_DESTRUCTIVE and not exact:
            continue   # clear/delete actions only against the exact visible generation
        if cmd=='SET' and len(parts)>=5:
            changed=_apply_setting(parts[1],parts[2],parts[3],parts[4]) or changed
        elif cmd=='VIEW' and len(parts)>=3:
            ctx=active_context(); storage=str(ctx.get('storage_key') or '')
            if not storage: continue
            view=_load_view(storage); field=parts[1]; value='|'.join(parts[2:])
            if field in {'myclub','ascending'}: view[field]=value.lower() in {'1','true','yes','on'}
            elif field in {'ovr_min','ovr_max','pot_min','pot_max','age_min','age_max','ps_min','limit','sort_column','selected_pid','event_limit','face_picker','face_limit','face_page_size'}:
                try:view[field]=int(value)
                except Exception:continue
            elif field in DEFAULT_VIEW: view[field]=value
            if field in {'ovr_ranges','pot_ranges'}: view[field.replace('_ranges','_min')]=0; view[field.replace('_ranges','_max')]=0
            if field=='face_region': view['face_limit']=0
            if field=='face_picker': view['face_region']=''; view['face_limit']=0
            if field not in {'limit','selected_pid','sort_column','ascending','history_path','face_picker','face_region','face_limit','face_page_size'}: view['limit']=PAGE_SIZE
            view['storage_key']=storage; _save_view(view); changed=True
        elif cmd=='SELECT' and len(parts)>=2:
            ctx=active_context(); storage=str(ctx.get('storage_key') or '')
            if not storage:continue
            view=_load_view(storage)
            view['history_path']=''; view['face_picker']=0
            try:view['selected_pid']=int(parts[1])
            except Exception:view['selected_pid']=0
            _save_view(view); changed=True
        elif cmd=='FACE' and len(parts)>=3 and face_lib.faces_visible():
            # v1.24.32: face picked in the overlay (or AUTO). Queued beside the world file;
            # the next checkpoint moves it into the career's world.
            ctx=active_context(); storage=str(ctx.get('storage_key') or '')
            if not storage: continue
            try:
                w=active_world() or {}
                player=(w.get('players') or {}).get(str(int(parts[1])))
                rel='|'.join(parts[2:]).strip()
                if player and rel:
                    if rel!=face_lib.AUTO:
                        fs=face_lib.face_settings(); idx=face_lib.load_library(fs['face_library_path'])
                        if not any(rel in files for g in ('M','F') for files in idx.get(g,{}).values()): continue
                    changed=face_lib.save_choice(_face_choices_path(storage),player,rel) or changed
            except Exception: pass
        elif cmd=='CLEAR_EVENTS':
            continue   # v1.24.30: clearing event history was removed (it is used for acquisition sources)
        elif cmd=='ACTION' and len(parts)>=2:
            action=parts[1].strip().lower()
            if action=='clear_events':
                continue   # v1.24.30: removed
            elif action=='clear_logs':
                try:
                    LOG_ROOT.mkdir(parents=True,exist_ok=True)
                    for fp in LOG_ROOT.rglob('*'):
                        if fp.is_file(): fp.unlink(missing_ok=True)
                    changed=True
                except Exception: pass
            elif action=='delete_current_data':
                try: changed=bool(delete_current_data()) or changed
                except Exception: pass
    if changed:
        try:
            storage=str(active_context().get('storage_key') or '')
            if storage: changed=_enforce_non_debug_limits(storage) or changed
        except Exception: pass
    return changed
