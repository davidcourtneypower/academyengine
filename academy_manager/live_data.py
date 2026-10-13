from __future__ import annotations
from fc27_academy.fsutil import replace_retry
import json, re, shutil
from pathlib import Path
from fc27_academy.nationalities import nationality_name
from fc27_academy.playstyle_development_planner import current_styles
from fc27_academy.runtime_config import normal_threshold, plus_threshold, career_settings_path
from fc27_academy.settings import Settings as AcademySettings
from fc27_academy.paths import CONFIG_ROOT
from fc27_academy.playstyle_acquisition_control import audit_world as audit_normal_acquisition
from fc27_academy.playstyle_plus_acquisition_control import audit_world as audit_plus_acquisition
from fc27_academy.role_acquisition_control import audit_world as audit_role_acquisition
from fc27_academy.paths import BRIDGE_ROOT, ACADEMY_STATE_ROOT, EVENTS_ROOT
from fc27_academy.event_engine import load_events, mark_all_read, clear_events
from fc27_academy.save_restore_points import clear_event_history_from_restore_points
from fc27_academy.role_sync import decode_role

STATE_ROOT = ACADEMY_STATE_ROOT / 'saves'



def _thresholds_for_storage(storage_key:str):
    try:
        cp=career_settings_path(storage_key)
        st=AcademySettings(path=cp,base_path=CONFIG_ROOT/'academy_settings.json')
        prod=st.data.get('production') or {}
        nt=max(50.0,min(200.0,float(prod.get('normal_playstyle_threshold',100.0))))
        pt=max(nt,max(100.0,min(360.0,float(prod.get('playstyle_plus_threshold',180.0)))))
        return nt,pt
    except Exception:
        return normal_threshold(),plus_threshold()

POSITION_NAMES={
0:'GK',1:'SW',2:'RWB',3:'RB',4:'RCB',5:'CB',6:'LCB',7:'LB',8:'LWB',9:'RDM',10:'CDM',11:'LDM',12:'RM',13:'RCM',14:'CM',15:'LCM',16:'LM',17:'RAM',18:'CAM',19:'LAM',20:'RF',21:'CF',22:'LF',23:'RW',24:'RS',25:'ST',26:'LS',27:'LW'
}


def _dob_text(g:dict)->str:
    d=g.get('dob') or {}
    try:
        if all(d.get(k) is not None for k in ('day','month','year')):
            return f"{int(d['day']):02d}/{int(d['month']):02d}/{int(d['year']):04d}"
    except Exception:pass
    return '—'


def active_context():
    p=BRIDGE_ROOT/'active_context.lua'
    if not p.exists():return {}
    try:s=p.read_text(encoding='utf-8')
    except Exception:return {}
    out={}
    for k in ('career_uid','branch_id','storage_key','reason'):
        m=re.search(rf'{k}="([^"]*)"',s)
        if m:out[k]=m.group(1)
    out['writes_held']='writes_held=true' in s
    return out


def active_storage_key():
    return active_context().get('storage_key') or ''




def world_for_storage(storage_key: str):
    key=str(storage_key or '').strip()
    if not key:return None
    p=STATE_ROOT/key/'generated_world.json'
    if not p.exists():return None
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return None

def events_for_storage(storage_key: str, mark_read: bool=False):
    key=str(storage_key or '').strip()
    if not key:return []
    rows=load_events(key)
    rows.sort(key=lambda e:int(e.get('created_at',0) or 0), reverse=True)
    if mark_read:mark_all_read(key)
    return rows

def clear_events_for_storage(storage_key: str):
    key=str(storage_key or '').strip()
    if not key:return False
    clear_events(key)
    # Keep explicit history clearing durable across later save rewinds as well.
    try: clear_event_history_from_restore_points(key)
    except Exception: pass
    # Acquisition milestones are also mirrored in durable player history so older
    # builds can recover missing event rows. If the user explicitly clears Event
    # History those mirrors must be removed too, otherwise Events/Timeline simply
    # reconstruct the rows on the next overlay refresh. Technical age/lifecycle
    # history remains intact because the engine uses it for development evidence.
    wp=STATE_ROOT/key/'generated_world.json'
    try:
        world=json.loads(wp.read_text(encoding='utf-8'))
        changed=False
        removable={'PLAYSTYLE_PRODUCTION_COMMIT','PLAYSTYLE_PLUS_PRODUCTION_COMMIT','PLUS_PRODUCTION_COMMIT','ROLE_PRODUCTION_COMMIT'}
        for player in (world.get('players') or {}).values():
            hist=player.get('history') or []
            kept=[h for h in hist if not (isinstance(h,dict) and str(h.get('type') or '').upper() in removable)]
            if len(kept)!=len(hist): player['history']=kept; changed=True
        if changed:
            tmp=wp.with_suffix(wp.suffix+'.tmp'); tmp.write_text(json.dumps(world,separators=(',',':'),sort_keys=True),encoding='utf-8'); replace_retry(tmp,wp)
    except Exception:
        pass
    return True

def list_saved_careers():
    out=[]
    if not STATE_ROOT.exists():return out
    try:
        from . import read_model
    except Exception:
        read_model=None
    for d in STATE_ROOT.iterdir():
        if not d.is_dir():continue
        p=d/'generated_world.json'
        if not p.exists():continue
        try:
            meta=read_model.career_meta(d.name) if read_model else {}
            if meta:
                out.append({
                    'storage_key':d.name,'career_uid':meta.get('career_uid') or '',
                    'branch_id':meta.get('branch_id') or '', 'team_name':meta.get('team_name') or 'Unknown club',
                    'season':meta.get('season') or 'Career','date_text':meta.get('date_text') or '—',
                    'player_count':int(meta.get('player_count') or 0),'season_epoch':meta.get('season_epoch',0),
                    'modified_at':p.stat().st_mtime,
                });continue
            # First-time fallback before a save has ever been indexed by the UI.
            w=json.loads(p.read_text(encoding='utf-8'));c=dict(w.get('career') or {});dt=c.get('date') or {};date_text='—'
            if all(isinstance(dt.get(k),int) for k in ('day','month','year')):
                date_text=f"{int(dt['day']):02d}/{int(dt['month']):02d}/{int(dt['year']):04d}"
            out.append({'storage_key':d.name,'career_uid':w.get('career_uid') or c.get('career_uid') or '',
                'branch_id':w.get('branch_id') or c.get('branch_id') or '','team_name':c.get('team_name') or 'Unknown club',
                'season':c.get('season') or c.get('season_id') or 'Career','date_text':date_text,
                'player_count':len(w.get('players') or {}),'season_epoch':w.get('season_epoch',0),'modified_at':p.stat().st_mtime})
        except Exception:continue
    out.sort(key=lambda x:float(x.get('modified_at') or 0), reverse=True)
    return out

def career_for_storage(storage_key: str):
    w=world_for_storage(storage_key) or {}
    c=dict(w.get('career') or {})
    c.update({
        'career_uid':w.get('career_uid') or c.get('career_uid') or '',
        'branch_id':w.get('branch_id') or c.get('branch_id') or '',
        'storage_key':w.get('storage_key') or storage_key or '',
        'player_count':len(w.get('players') or {}),
        'season_epoch':w.get('season_epoch',0),
    })
    return c

# v1.24.13: one parsed copy per world-file revision. A 7,000-player world is ~30 MB of
# JSON and each publication parsed it two or three times (about 1.2 s of the 3.8 s
# publications in the 08-10 bridge.log). Readers here treat the world as read-only;
# the only in-place updates (lifetime-policy defaults) are idempotent.
_WORLD_CACHE: dict[str, tuple[int, int, dict]] = {}

def _load_world_file(p: Path):
    try:
        st=p.stat()
    except OSError:
        return None
    hit=_WORLD_CACHE.get(str(p))
    if hit and hit[0]==st.st_mtime_ns and hit[1]==st.st_size:
        return hit[2]
    try:
        w=json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None
    try:
        st2=p.stat()
        if (st2.st_mtime_ns,st2.st_size)==(st.st_mtime_ns,st.st_size):
            _WORLD_CACHE.clear(); _WORLD_CACHE[str(p)]=(st.st_mtime_ns,st.st_size,w)
    except OSError:
        pass
    return w

def active_world():
    key=active_storage_key()
    if not key:return None
    return _load_world_file(STATE_ROOT/key/'generated_world.json')


def current_career(world:dict|None=None):
    w=(world if world is not None else active_world()) or {}
    c=dict(w.get('career') or {})
    ctx=active_context()
    c.update({
        'career_uid':w.get('career_uid') or ctx.get('career_uid') or '',
        'branch_id':w.get('branch_id') or ctx.get('branch_id') or '',
        'storage_key':w.get('storage_key') or ctx.get('storage_key') or '',
        'player_count':len(w.get('players') or {}),
        'season_epoch':w.get('season_epoch',0),
    })
    return c


def delete_storage_data(storage_key: str):
    key=str(storage_key or "").strip()
    if not key:return False
    target=STATE_ROOT/key
    if target.exists():shutil.rmtree(target)
    # Clear branch event history and only transient files for this active storage.
    ep=EVENTS_ROOT/key
    if ep.exists():shutil.rmtree(ep)
    tp=BRIDGE_ROOT/'saves'/key
    if tp.exists():shutil.rmtree(tp)
    return True


def career_storage_keys(career_uid: str) -> list[str]:
    """Every branch of a career that has engine data (storage keys are <career_uid> or <career_uid>__...)."""
    uid=str(career_uid or '').strip()
    if not uid: return []
    out=set()
    for root in (STATE_ROOT, EVENTS_ROOT, BRIDGE_ROOT/'saves'):
        try:
            for d in root.iterdir():
                if d.is_dir() and (d.name==uid or d.name.startswith(uid+'__')): out.add(d.name)
        except OSError:
            pass
    return sorted(out)


def delete_current_data():
    """Delete all Academy Engine data of the career loaded in FC27 (v1.0.3: every branch, the
    stored checkpoints and save anchors, and the overlay cache; it used to remove only the
    current branch's files, so the overlay kept showing it and an older save could restore it).
    Career settings are kept. The players are rebuilt from FC27 at the next in-game day or save,
    as already-known players (no second round of starting PlayStyles)."""
    import json as _json, time as _time
    from fc27_academy.paths import DELETED_CAREERS_ROOT
    from fc27_academy.transaction_store import purge_career, set_lifecycle, lifecycle
    from . import read_model
    ctx=active_context(); key=str(ctx.get('storage_key') or '')
    world=active_world() or {}
    uid=str(ctx.get('career_uid') or world.get('career_uid') or '').strip()
    if not key and not uid: return False
    keys=sorted(set(career_storage_keys(uid))|({key} if key else set()))
    # v1.0.4: remember who the career's players were, so only those same players are rebuilt as
    # already known (a new career that happens to reuse the save ID is treated normally).
    from fc27_academy.world_bootstrap_store import IDENTITY_KEYS
    marker_path=DELETED_CAREERS_ROOT/(re.sub(r'[^A-Za-z0-9_-]','_',uid)+'.json') if uid else None
    known={}
    try:
        if marker_path and marker_path.exists():
            known.update((_json.loads(marker_path.read_text(encoding='utf-8')) or {}).get('players') or {})
    except Exception:
        pass
    for k in keys:
        try:
            w=_json.loads((STATE_ROOT/k/'generated_world.json').read_text(encoding='utf-8'))
        except Exception:
            continue
        for pid,p in (w.get('players') or {}).items():
            g=(p or {}).get('game') or {}
            known[str(pid)]={f:g.get(f) for f in IDENTITY_KEYS if g.get(f) is not None}
    for k in keys: delete_storage_data(k)
    purge_career(uid,keys)
    read_model.forget_storage(keys)
    if uid:
        DELETED_CAREERS_ROOT.mkdir(parents=True,exist_ok=True)
        marker_path.write_text(_json.dumps({'career_uid':uid,'deleted_at':_time.time(),'storage_keys':keys,'players':known}),encoding='utf-8')
    life=lifecycle()
    set_lifecycle('CAREER_LOADING',detail='Academy Engine data for this career was deleted. It is rebuilt from FC27 at the next in-game day or save.',
                  runtime_session=str(life.get('runtime_session') or ''),career_uid=uid,storage_key=key,branch_id=str(ctx.get('branch_id') or ''),
                  request_id='',career_date=life.get('career_date') or {},snapshot_sequence=int(life.get('snapshot_sequence') or 0),generation=0)
    return True


def clear_current_events():
    return clear_events_for_storage(active_storage_key())

def current_events(mark_read=False):
    return events_for_storage(active_storage_key(), mark_read=mark_read)


def player_rows(world:dict|None=None):
    world=world or active_world()
    if not world:return []
    key=world.get('storage_key') or active_storage_key(); nt,pt=_thresholds_for_storage(str(key or '')); out=[]
    career=world.get('career') or {}; user_teamid=career.get('user_teamid')
    try:
        acq=audit_normal_acquisition(world)
    except Exception:
        acq={}
    hold_by_path={}
    for bucket in ('held_cooldown','held_lifetime','held_position','suppressed'):
        for h in (acq.get(bucket) or []):
            hold_by_path[(int(h.get('playerid',0)),str(h.get('style')))] = dict(h)
    winner_by_path={(int(h.get('playerid',0)),str(h.get('style'))):dict(h) for h in (acq.get('winners') or [])}
    events_by_player={}
    if key:
        for ev in load_events(str(key)):
            try: events_by_player.setdefault(int(ev.get('playerid')),[]).append(ev)
            except Exception: pass
    try:
        from fc27_academy.runtime_config import decline as _decline_cfg
        _dc=_decline_cfg(); _decline_on=bool(_dc.get('playstyle_loss_enabled') or _dc.get('playstyle_plus_loss_enabled'))
    except Exception:
        _decline_on=False
    for p in (world.get('players') or {}).values():
        if p.get('retired'): continue   # v1.24.36: retired players are hidden completely
        g=p.get('game') or {}; e=p.get('engine') or {}
        normal,plus,_=current_styles(g)
        np=e.get('playstyle_progress') or {}; pp=e.get('playstyle_plus_progress') or {}
        neligible=[(k,v) for k,v in np.items() if k not in normal]
        peligible=[(k,v) for k,v in pp.items() if k in normal and k not in plus]
        next_ps=max(neligible,key=lambda kv:float(kv[1]),default=(None,0.0))
        # When one or more paths are ready, display the path the production acquisition
        # gate actually ranks first, not merely the largest stored percentage.
        pid_hint=int(p.get('playerid',0) or 0)
        ranked=[(style,float(val or 0)) for style,val in neligible if (pid_hint,str(style)) in winner_by_path]
        if ranked: next_ps=max(ranked,key=lambda kv:float(kv[1]))
        next_plus=max(peligible,key=lambda kv:float(kv[1]),default=(None,0.0))
        nmeta=(e.get('playstyle_progress_meta') or {}).get(next_ps[0],{}) if next_ps[0] else {}
        pmeta=(e.get('playstyle_plus_progress_meta') or {}).get(next_plus[0],{}) if next_plus[0] else {}
        dev_count=int(e.get('playstyle_development_checkpoint_count',0) or 0)
        nlast=int(nmeta.get('last_checkpoint_count',0) or 0); plast=int(pmeta.get('last_checkpoint_count',0) or 0)
        cap=int(e.get('playstyle_lifetime_normal_cap')) if e.get('playstyle_lifetime_normal_cap') is not None else 7   # 0 is valid after decline
        pid=int(p.get('playerid',0))
        name=g.get('name') or f'Generated Player #{pid}'
        club=g.get('clubname') or (career.get('team_name') if g.get('clubteamid')==user_teamid else '') or 'Unknown club'
        pos=POSITION_NAMES.get(int(g.get('preferredposition1',-1)),str(g.get('preferredposition1','?')))
        current_roles=[]
        raw_roles=list(g.get('roles') or [])
        if not raw_roles: raw_roles=[g.get(rf,0) for rf in ('role1','role2','role3','role4','role5')]
        for raw_role in raw_roles:
            try:
                rv=int(raw_role or 0)
                if rv:
                    label=decode_role(rv)
                    if not label.startswith('UNKNOWN(') and label not in current_roles: current_roles.append(label)
            except Exception:
                pass
        at_cap=len(normal)>=cap
        ready_status='Lifetime cap reached' if at_cap else ('Developing' if float(next_ps[1] or 0)>0 else 'No active PlayStyle progress')
        ready_detail=(f'{len(normal)} / {cap} PlayStyles — stored candidate progress is retained as history only.' if at_cap else '')
        if at_cap:
            next_ps=(None,0.0); nmeta={}
        elif next_ps[0] and float(next_ps[1] or 0) >= nt:
            path_key=(pid,str(next_ps[0]))
            hold=hold_by_path.get(path_key) or {}
            win=winner_by_path.get(path_key) or {}
            validation=str(hold.get('validation') or win.get('validation') or '')
            if int(e.get('playstyle_acquisition_cooldown_days_remaining',0) or 0)>0 or validation=='HOLD_ACQUISITION_COOLDOWN':
                days=int(e.get('playstyle_acquisition_cooldown_days_remaining',0) or hold.get('cooldown_days_remaining',0) or 0)
                ready_status='Ready — Cooldown'
                ready_detail=f'{days} days remaining' if days else 'Waiting for acquisition cooldown'
            elif validation=='HOLD_LIFETIME_PLAYSTYLE_CAP':
                ready_status='Held — Lifetime cap reached'
                ready_detail=f"{len(normal)} / {cap} PlayStyles"
            elif validation=='HOLD_PLAUSIBILITY':
                fit=float(hold.get('attribute_fit',0) or 0)
                chance=float(hold.get('near_fit_chance',0) or 0)
                if chance>0:
                    ready_status='Ready — Unusual fit, chance each checkpoint'
                    ready_detail=(f"This PlayStyle is unusual for the player’s positions. Supporting attributes average {fit:.1f}. "
                                  f"Current award chance is {chance:.0f}% at each checkpoint. At 78 it qualifies automatically. Progress is preserved at 100%.")
                else:
                    ready_status='Ready — Unusual fit, attributes still too low'
                    ready_detail=(f"This PlayStyle is unusual for the player’s positions. Supporting attributes average {fit:.1f}. "
                                  "An average of 70 enters the chance window; 78 qualifies automatically. Progress is preserved at 100%.")
            elif validation=='HOLD_COMPETING_READY_PATH':
                ready_status='Ready — Another completed path currently ranks higher'
                ready_detail='Candidate ranking is recalculated from current attributes.'
            elif validation=='HOLD_MAPPING':
                ready_status='Held — Write mapping unavailable'
                ready_detail='Academy Engine will not write an unverified PlayStyle mapping.'
            else:
                ready_status='Ready — Queued for acquisition'
                ready_detail='Development is complete and this is the player’s highest-ranked eligible path. Academy Engine will attempt it at the next available production write slot.'

        from fc27_academy.role_acquisition_control import _field_changes
        role_values=[float(v or 0) for k,v in (e.get('role_progress') or {}).items() if _field_changes(g,str(k))]
        lane_status=[]
        if float(next_ps[1] or 0)>0 and not at_cap: lane_status.append('PlayStyle: '+ready_status)
        def award_state(audit, lane):
            small_world=dict(world); small_world['players']={str(pid):p}
            gate=audit(small_world)
            for bucket,label in (('held_cooldown','Cooldown'),('held_lifetime','Eligibility/cap hold'),('held_plausibility','Attribute fit hold'),('mapping_held','Mapping hold')):
                if gate.get(bucket): return label
            winner=(gate.get('winners') or [{}])[0]
            if winner.get('validation')=='HOLD_MAPPING': return 'Mapping hold'
            return 'Queued' if gate.get('verified_candidates') else 'Not eligible'
        plus_status=('Developing' if float(next_plus[1] or 0)<pt else award_state(audit_plus_acquisition,'PlayStyle+')) if next_plus[0] else 'No active PlayStyle+ progress'
        if float(next_plus[1] or 0)>0: lane_status.append('PlayStyle+: '+plus_status)
        role_status=('Developing' if max(role_values)<100 else award_state(audit_role_acquisition,'Role')) if role_values and max(role_values)>0 else 'No active Role++ progress'
        if role_values and max(role_values)>0: lane_status.append('Role++: '+role_status)
        # v1.24.36: decline phase (shown only once it has started and loss is switched on).
        _dec=e.get('decline') or {}
        decline_active=bool(_dec.get('active')) and _decline_on
        if decline_active: lane_status.append(f"Decline phase active (since {_dec.get('active_since_age')})")
        if p.get('lifecycle')=='FREE_AGENT': overall_status='Paused — Free agent'
        elif not p.get('observed_this_checkpoint',False): overall_status='Paused — Not observed'
        elif p.get('lifecycle')!='CLUB': overall_status='Paused — Outside club'
        else: overall_status=' | '.join(lane_status) or 'No active progress'

        out.append({
            'playerid':pid,'name':name,'club':club,'clubteamid':g.get('clubteamid'),'normal_threshold':nt,'plus_threshold':pt,
            'is_user_team':bool(g.get('is_user_team')) if g.get('is_user_team') is not None else bool(user_teamid and g.get('clubteamid')==user_teamid),
            'position':pos,'position_id':g.get('preferredposition1'),
            'nationality':g.get('nationality'),'nationality_label':nationality_name(g.get('nationality')),
            'dob':dict(g.get('dob') or {}),'dob_text':_dob_text(g),'birthdate_raw':g.get('birthdate'),'leagueid':g.get('leagueid'),
            'age':g.get('age','—'),'ovr':g.get('overallrating','—'),'potential':g.get('potential','—'),
            'lifecycle':p.get('lifecycle','—'),'observed_this_checkpoint':bool(p.get('observed_this_checkpoint',False)),'normal_styles':sorted(normal),'plus_styles':sorted(plus),'roles':current_roles,
            'normal_count':len(normal),'plus_count':len(plus),'cap':cap,
            'plus_eligible':bool(e.get('playstyle_plus_lifetime_eligible',False)),
            'next_ps':next_ps[0], 'next_ps_value':float(next_ps[1] or 0), 'next_ps_pct':min(100.0,100.0*float(next_ps[1] or 0)/nt) if nt else 0,
            'normal_progress_paths':sorted([{'style':str(k),'value':float(v or 0),'pct':min(100.0,100.0*float(v or 0)/nt) if nt else 0,'owned':k in normal} for k,v in np.items()],key=lambda x:-x['value']),
            'status':overall_status,'next_ps_status':ready_status,'next_ps_status_detail':ready_detail,
            'next_ps_meta':dict(nmeta),'next_ps_checkpoints_since':max(0,dev_count-nlast) if nlast else None,
            'next_plus':next_plus[0], 'next_plus_value':float(next_plus[1] or 0), 'next_plus_pct':min(100.0,100.0*float(next_plus[1] or 0)/pt) if pt else 0,
            'plus_progress_paths':sorted([{'style':str(k),'value':float(v or 0),'pct':min(100.0,100.0*float(v or 0)/pt) if pt else 0,'owned':k in plus} for k,v in pp.items()],key=lambda x:-x['value']),
            'next_plus_status':plus_status,'role_status':role_status,'next_plus_meta':dict(pmeta),'next_plus_checkpoints_since':max(0,dev_count-plast) if plast else None,
            'development_checkpoint_count':dev_count,
            'decline_active':decline_active,'decline_since':_dec.get('active_since_age') if decline_active else None,
            'normal_cooldown':int(e.get('playstyle_acquisition_cooldown_days_remaining',0) or 0),
            'plus_cooldown':int(e.get('playstyle_plus_cooldown_days_remaining',0) or 0),
            'role_cooldown':int(e.get('role_acquisition_cooldown_days_remaining',0) or 0),
            'active_role_progress':{k:v for k,v in (e.get('role_progress') or {}).items() if _field_changes(g,str(k))},'role_progress':dict(e.get('role_progress') or {}),'history':list(p.get('history') or []),
            'events':sorted(events_by_player.get(pid,[]),key=lambda x:int(x.get('created_at',0))), 'raw':p,
        })
    return sorted(out,key=lambda x:(not x['is_user_team'],-float(x['next_ps_pct']),-int(x['ovr']) if isinstance(x['ovr'],int) else 0,x['name']))


def find_player(pid:int):
    for r in player_rows():
        if int(r.get('playerid',-1))==int(pid):return r
    return None
