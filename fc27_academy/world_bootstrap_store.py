"""Persistent world state for FC27 generated players.

Existing careers are adopted from current FC27 state. Subsequent snapshots are
checkpoint evidence: identity/DNA persists, lifecycle transitions are recorded,
and verified FC27 attribute gains feed role-development evidence. This module
never writes FC27.
"""
from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from pathlib import Path
import json, os
from .existing_career_bootstrap import bootstrap_existing_player
from .checkpoint_engine import ingest_checkpoint
from .evolution_evidence import observe as observe_evolution
from .playstyle_development_planner import update_from_evidence as update_playstyle_evidence
from .playstyle_lifetime import ensure_policy
from .evolution_staging import _semantic as _role_semantic


def native_role_upgrades(player: dict, old_game: dict, snap: dict) -> list[dict]:
    """Role+ -> Role++ upgrades FC27 made itself between two observed snapshots (v1.24.26).

    A slot that held Role+ id N (1..52) and now holds N+100 is an upgrade. Upgrades the
    engine wrote are excluded via the player's ROLE_PRODUCTION_COMMIT history."""
    def ints(v):
        out=[]
        for x in list(v or []):
            try: out.append(int(x))
            except (TypeError,ValueError): pass
        return out
    old=ints(old_game.get('roles')); new=ints(snap.get('roles'))
    if not old or not new: return []
    engine_written=set()
    for h in player.get('history') or []:
        if isinstance(h,dict) and h.get('type')=='ROLE_PRODUCTION_COMMIT':
            try: engine_written.add(int(h.get('proposed')))
            except (TypeError,ValueError): pass
    out=[]
    for nv in new:
        if not (101<=nv<=152) or nv in old or (nv-100) not in old or nv in engine_written: continue
        name=_role_semantic(nv-100)
        if name: out.append({'role':name,'role_id':nv,'from_role_id':nv-100})
    return out
from .runtime_config import normal_cooldown_days, plus_cooldown_days, role_cooldown_days

SCHEMA_VERSION=6


def _identity_replacement_evidence(oldg:dict,snap:dict):
    """Return (replace, reasons) using conservative immutable evidence.

    FC27 can re-encode birthdate and name-ID metadata during season transitions.
    Those two changing together are therefore *not* enough to destroy durable
    Academy progression when nationality is stable and the player ages forward.

    A replacement is accepted when either:
      * nationality changes together with birthdate/name identity evidence, or
      * the player becomes materially younger (ID reuse) together with identity evidence.
    """
    birth_changed=(oldg.get('birthdate') is not None and snap.get('birthdate') is not None and oldg.get('birthdate')!=snap.get('birthdate'))
    nat_changed=(oldg.get('nationality') is not None and snap.get('nationality') is not None and oldg.get('nationality')!=snap.get('nationality'))
    name_keys=('firstnameid','lastnameid','commonnameid','playerjerseynameid')
    comparable=[k for k in name_keys if oldg.get(k) is not None and snap.get(k) is not None]
    name_changed=bool(comparable and any(oldg.get(k)!=snap.get(k) for k in comparable))
    try:
        old_age=float(oldg.get('age')); new_age=float(snap.get('age'))
        age_rewind=(new_age <= old_age-2.0)
    except (TypeError,ValueError):
        age_rewind=False
    reasons=[]
    if birth_changed: reasons.append('birthdate')
    if nat_changed: reasons.append('nationality')
    if name_changed: reasons.append('name_ids')
    if age_rewind: reasons.append('age_rewind')
    supporting=(birth_changed or name_changed)
    replace=bool((nat_changed and supporting) or (age_rewind and (supporting or nat_changed)))
    return replace, sorted(set(reasons))

RETIRE_MIN_AGE=33
RETIRE_MISSING_CHECKPOINTS=3
RETIRE_MIN_MISSING_DAYS=7        # missing across at least a week of career time, not just saves/reloads
RETIRED_TRIM_SEASONS=2
_RETIRED_KEEP_GAME=('playerid','name','birthdate','nationality','gender','age','overallrating','potential','preferredposition1','dob','trait1','trait2','icontrait1','icontrait2')

def _career_ordinal(d):
    try:
        import datetime as _dt
        return _dt.date(int(d['year']),int(d['month']),int(d['day'])).toordinal()
    except Exception:
        return None

def _retired_engine_keep(e:dict)->dict:
    """What a trimmed retired record keeps: lifetime policy (cap, PlayStyle+ eligibility, rolls),
    Football DNA, face and decline history, so a player seen again resumes exactly as he was."""
    keep={k:v for k,v in e.items() if k.startswith(('playstyle_lifetime','playstyle_plus_lifetime')) or k in ('football_dna','face')}
    d=e.get('decline') or {}
    if d: keep['decline']={k:v for k,v in d.items() if k not in ('status','progress','ready')}
    return keep

def update_retirements(data:dict,seen:set,previously_observed:set,checkpoint_id,career_meta=None)->dict:
    """Mark older players FC27 no longer holds as retired; trim long-retired records.

    A snapshot only counts towards retirement when it is trusted: not empty and at least half
    the size of the last trusted snapshot (a stable reference, so several partial snapshots
    in a row cannot lower the bar for each other)."""
    out={'retired':0,'trimmed':0,'trusted':True}
    ref=int(data.get('retirement_reference_count') or 0) or len(previously_observed)
    trusted=len(seen)>0 and (ref<=0 or len(seen)>=0.5*ref)
    out['trusted']=trusted
    # The reference only rises (yearly intakes raise it), so a run of shrinking snapshots can
    # never lower the bar step by step.
    if trusted: data['retirement_reference_count']=max(ref,len(seen))
    epoch=int(data.get('season_epoch',0) or 0)
    date=dict((career_meta or {}).get('date') or {}) if isinstance(career_meta,dict) else {}
    today=_career_ordinal(date)
    for key,p in data.get('players',{}).items():
        if key in seen: continue
        if trusted:
            p['missing_checkpoints']=int(p.get('missing_checkpoints',0) or 0)+1
            if p.get('missing_since_ordinal') is None and today is not None: p['missing_since_ordinal']=today
        r=p.get('retired')
        if r is None:
            age=p.get('last_seen_age',(p.get('game') or {}).get('age'))
            try: age=int(age)
            except (TypeError,ValueError): continue
            since=p.get('missing_since_ordinal')
            # Without a career date nobody is retired (saves/reloads on one day must not count).
            days_ok=(today is not None and since is not None and today-int(since)>=RETIRE_MIN_MISSING_DAYS)
            if age>=RETIRE_MIN_AGE and int(p.get('missing_checkpoints',0) or 0)>=RETIRE_MISSING_CHECKPOINTS and days_ok:
                p['retired']={'checkpoint_id':checkpoint_id,'age':age,'season_epoch':epoch,'career_date':date}
                p.setdefault('history',[]).append({'type':'RETIRED','checkpoint_id':checkpoint_id,'age':age})
                out['retired']+=1
        elif not r.get('trimmed') and epoch-int(r.get('season_epoch') if r.get('season_epoch') is not None else epoch)>=RETIRED_TRIM_SEASONS:
            g=p.get('game') or {}; e=p.get('engine') or {}
            p['game']={k:g.get(k) for k in _RETIRED_KEEP_GAME if k in g}
            p['engine']=_retired_engine_keep(e)
            p['history']=[]
            r['trimmed']=True; out['trimmed']+=1
    return out

def _progress_ledgers(engine:dict):
    return {k:dict(engine.get(k) or {}) for k in ('playstyle_progress','playstyle_plus_progress','role_progress')}

def _restore_progress_floor(engine:dict,before:dict):
    """Never lose earned progression during ordinary reconciliation/season rollover.

    Confirmed production receipts reset their ledger before the next snapshot, so
    this guard does not interfere with legitimate acquisitions. It only prevents
    an ingest/reconciliation pass from lowering already-durable progress.
    """
    restored=[]
    for ledger,oldmap in (before or {}).items():
        cur=engine.setdefault(ledger,{})
        for key,old in oldmap.items():
            try: oldv=float(old); curv=float(cur.get(key,0) or 0)
            except (TypeError,ValueError): continue
            if curv + 1e-9 < oldv:
                cur[key]=old
                restored.append((ledger,str(key),curv,oldv))
    return restored

def _atomic(path:Path,obj:dict):
    from .path_history_store import externalize
    externalize(obj)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8')
    replace_retry(tmp,path)

from .path_history_store import batched_history

IDENTITY_KEYS=('birthdate','nationality','firstnameid','lastnameid','commonnameid','playerjerseynameid','age')


def _deleted_career_players(career_uid):
    """Players this career had when the user deleted its engine data (v1.0.3, live_data.delete_current_data).

    None when the career's data was never deleted. Otherwise {playerid: identity}; v1.0.4 records
    each player's identity so only those same players come back as already known. A marker from
    v1.0.3 has no player list and returns {'*': {}} (every player treated as known, as before).
    """
    if not career_uid: return None
    import re as _re
    from .paths import DELETED_CAREERS_ROOT
    f=DELETED_CAREERS_ROOT/(_re.sub(r'[^A-Za-z0-9_-]','_',str(career_uid))+'.json')
    if not f.exists(): return None
    try: marker=json.loads(f.read_text(encoding='utf-8'))
    except Exception: return None
    players=marker.get('players')
    return {'*':{}} if not isinstance(players,dict) else {str(k):(v if isinstance(v,dict) else {}) for k,v in players.items()}


def _known_before_delete(deleted,pid,snap) -> bool:
    """True when this player existed in the career before its engine data was deleted (same person, not a reused ID)."""
    if not deleted: return False
    if '*' in deleted: return True
    ident=deleted.get(str(pid))
    if ident is None: return False
    return not _identity_replacement_evidence(ident,snap)[0]


class WorldBootstrapStore:
    def __init__(self,root:Path|str): self.root=Path(root)
    def path_for(self,save_uid):
        safe=''.join(c for c in str(save_uid) if c.isalnum() or c in '-_') or 'UNKNOWN_SAVE'
        
        return self.root/'saves'/safe/'generated_world.json'
    @batched_history
    def ingest(self,save_uid,players,checkpoint_id,request_id=None,runtime_session=None,day_epoch=None,career_uid=None,branch_id=None,career_meta=None,trigger=None,credit_development=True):
        path=self.path_for(save_uid)
        fresh_world=not path.exists()
        if not fresh_world: data=json.loads(path.read_text(encoding='utf-8'))
        else: data={'schema':SCHEMA_VERSION,'save_uid':str(save_uid),'players':{},'last_checkpoint_id':None,'processed_request_ids':[]}
        # v1.0.3: a career whose engine data the user deleted is rebuilt with its players as
        # already known, so nobody gets a second round of starting PlayStyles. v1.0.4: only the
        # players the career had at deletion (same identity); anyone else is new as normal.
        deleted_players=_deleted_career_players(career_uid) if fresh_world else None
        data['schema']=SCHEMA_VERSION
        data['save_uid']=str(save_uid)
        data['storage_key']=str(save_uid)
        if career_uid is not None: data['career_uid']=str(career_uid)
        if branch_id is not None: data['branch_id']=str(branch_id)
        if isinstance(career_meta,dict): data['career']=dict(career_meta)
        cleanup_removed=0
        # Session-relative day counters let the engine age cooldowns without relying
        # on an unverified FC27 date conversion. A restart never invents elapsed days.
        elapsed_days=0
        try: incoming_day=int(day_epoch) if day_epoch is not None else None
        except (TypeError,ValueError): incoming_day=None
        previous_session=data.get('runtime_session'); previous_day=data.get('runtime_day_epoch')
        # First checkpoint after a bridge/Lua runtime change is a baseline
        # re-sync only. We still adopt FC27's current live state, but we do NOT turn
        # unobserved offline attribute deltas into retroactive Role/PlayStyle progress.
        # This deliberately sacrifices at most one checkpoint of progression after a
        # restart in exchange for never inventing months of catch-up development.
        offline_rebase=bool(previous_session is not None and runtime_session is not None and str(previous_session)!=str(runtime_session))
        if runtime_session is not None and incoming_day is not None and str(previous_session)==str(runtime_session) and isinstance(previous_day,int):
            elapsed_days=max(0,incoming_day-previous_day)
        # GUI-tunable cooldowns are live policy. Lowering a configured maximum also
        # clamps an already-running cooldown; raising it never adds time back.
        ncap=normal_cooldown_days(); pcap=plus_cooldown_days(); rcap=role_cooldown_days()
        for cp in data.get('players',{}).values():
            ce=cp.setdefault('engine',{})
            rem=int(ce.get('playstyle_acquisition_cooldown_days_remaining',0) or 0)
            if rem>ncap: ce['playstyle_acquisition_cooldown_days_remaining']=ncap
            prem=int(ce.get('playstyle_plus_cooldown_days_remaining',0) or 0)
            if prem>pcap: ce['playstyle_plus_cooldown_days_remaining']=pcap
            rrem=int(ce.get('role_acquisition_cooldown_days_remaining',0) or 0)
            if rrem>rcap: ce['role_acquisition_cooldown_days_remaining']=rcap
        if elapsed_days:
            for cp in data.get('players',{}).values():
                ce=cp.setdefault('engine',{})
                rem=int(ce.get('playstyle_acquisition_cooldown_days_remaining',0) or 0)
                if rem>0: ce['playstyle_acquisition_cooldown_days_remaining']=max(0,rem-elapsed_days)
                prem=int(ce.get('playstyle_plus_cooldown_days_remaining',0) or 0)
                if prem>0: ce['playstyle_plus_cooldown_days_remaining']=max(0,prem-elapsed_days)
                rrem=int(ce.get('role_acquisition_cooldown_days_remaining',0) or 0)
                if rrem>0: ce['role_acquisition_cooldown_days_remaining']=max(0,rrem-elapsed_days)
        if runtime_session is not None: data['runtime_session']=str(runtime_session)
        if incoming_day is not None: data['runtime_day_epoch']=incoming_day
        processed=data.setdefault('processed_request_ids',[])
        # Request IDs are the durable idempotency key. Checkpoint IDs may restart
        # when Live Editor/Lua is restarted, so they are descriptive only.
        if request_id and request_id in processed:
            return {'status':'IDEMPOTENT_NOOP','incoming':len(players),'observed':0,'new':0,'returning':0,'missing':len(data['players']),'tracked':len(data['players']),'club':0,'free_agent':0,'other':0,'transitions':0,'role_signals':0,'reconciled':True,'path':str(path)}
        if request_id is None and data.get('last_checkpoint_id')==checkpoint_id:
            return {'status':'IDEMPOTENT_NOOP','incoming':len(players),'observed':0,'new':0,'returning':0,'missing':len(data['players']),'tracked':len(data['players']),'club':0,'free_agent':0,'other':0,'transitions':0,'role_signals':0,'reconciled':True,'path':str(path)}
        new=replaced_generation=club=free=other=transitions=role_signals=0; attribute_changes=potential_changes=playstyle_changes=0; playstyle_progress_events=playstyle_ready=playstyle_plus_ready=0; seen=set(); previously_observed={k for k,v in data['players'].items() if v.get('observed_this_checkpoint',False)}; returning=0
        # Loading/reloading/saving is reconciliation, not player development.
        # Academy progression may advance only on an actual settled career-day
        # transition. This makes save reloads idempotent and prevents a load screen
        # from generating passive training progress.
        # v1.24.10: credit development from evidence rather than the snapshot label.
        # v1.24.09 credited only DAY_SETTLED, so growth first observed by a save or
        # a mid-career boundary re-sync (85% of it in a real session) was discarded.
        # Growth counts when the caller confirmed branch continuity (no load, rewind
        # or exact-save restore) and FC27 actually advanced days in this same runtime
        # session. Pure reloads/saves without elapsed days never create progress.
        day_trigger=str(trigger or '').upper() in {'DAY_SETTLED','DAY_PASSED'}
        progression_trigger=bool(credit_development) and (day_trigger or elapsed_days>=1)
        training_days=max(1,min(31,int(elapsed_days or 0))) if progression_trigger else 0
        native_upgrades=[]
        for snap in players:
            pid=int(snap['playerid']); key=str(pid); seen.add(key)
            lifecycle=str(snap.get('lifecycle','CLUB'))
            club += lifecycle=='CLUB'; free += lifecycle=='FREE_AGENT'; other += lifecycle not in ('CLUB','FREE_AGENT')
            existing=data['players'].get(key)
            if existing is None:
                result,dna=bootstrap_existing_player(snap,career_seed=str(career_uid or save_uid),propose_initial_coherence=False)
                # DNA is stored once (engine.football_dna); every reader prefers it.
                existing={'playerid':pid,'dna_confidence':result.confidence,
                          'bootstrap_source':'ADOPTED_EXISTING_CAREER','first_checkpoint_id':checkpoint_id,
                          'engine':{'football_dna':dna,'role_progress':{}},'history':[],'game':dict(snap)}
                data['players'][key]=existing; new+=1
                rebuilt_after_delete=_known_before_delete(deleted_players,pid,snap)
                existing['generation_new_this_checkpoint']=not rebuilt_after_delete
                if rebuilt_after_delete: existing['bootstrap_source']='REBUILT_AFTER_DELETE'
                ensure_policy(existing)
            else:
                # A rewound/regenerated season can reuse generated player IDs for a different
                # person. Treat a changed immutable identity (birthdate or nationality) as a
                # replacement generation, never as months of development. This prevents
                # artificial season-boundary catch-up and resets only that replaced identity.
                oldg=existing.get('game') or {}
                identity_changed,identity_reasons=_identity_replacement_evidence(oldg,snap)
                if identity_changed:
                    result,dna=bootstrap_existing_player(snap,career_seed=str(career_uid or save_uid),propose_initial_coherence=False)
                    existing={'playerid':pid,'dna_confidence':result.confidence,
                              'bootstrap_source':'REGENERATED_ID_REBASE','first_checkpoint_id':checkpoint_id,
                              'engine':{'football_dna':dna,'role_progress':{}},'history':[{'type':'GENERATION_IDENTITY_REPLACED','checkpoint_id':checkpoint_id,'identity_reasons':identity_reasons}], 'game':dict(snap)}
                    data['players'][key]=existing; replaced_generation+=1
                    existing['generation_new_this_checkpoint']=True
                    existing['lifecycle']=lifecycle; existing['clubteamid']=snap.get('clubteamid'); existing['last_checkpoint_id']=checkpoint_id; existing['observed_this_checkpoint']=True
                    age=snap.get('age')
                    if isinstance(age,(int,float)): existing['history'].append({'type':'AGE_CHECKPOINT','checkpoint_id':checkpoint_id,'age':int(age)})
                    ensure_policy(existing)
                    continue
                existing['generation_new_this_checkpoint']=False
                # Migrate the duplicated top-level DNA copy into engine.football_dna.
                if 'dna' in existing:
                    legacy_dna=existing.pop('dna')
                    existing.setdefault('engine',{}).setdefault('football_dna',legacy_dna)
                progress_before=_progress_ledgers(existing.setdefault('engine',{}))
                if key not in previously_observed: returning+=1
                old_lifecycle=existing.get('lifecycle')
                ensure_policy(existing)
                # v1.24.26: note Role++ upgrades FC27 made itself (continuous timeline only;
                # a load/rewind compares against a different point in the career). They do
                # not start the engine's Role++ cooldown.
                if credit_development:
                    for up in native_role_upgrades(existing,existing.get('game') or {},snap):
                        existing.setdefault('history',[]).append({'type':'FC27_NATIVE_ROLE_UPGRADE','checkpoint_id':checkpoint_id,'career_date':dict((career_meta or {}).get('date') or {}) if isinstance(career_meta,dict) else {},**up})
                        native_upgrades.append({'playerid':pid,'player_name':snap.get('name') or (existing.get('game') or {}).get('name'),'club_name':snap.get('clubname'),'clubteamid':snap.get('clubteamid'),
                                                'position':snap.get('preferredposition1'),'age':snap.get('age'),'overall':snap.get('overallrating'),**up})
                evidence=observe_evolution(existing.get('game',{}),snap)
                attribute_changes += len(evidence['attribute_changes'])
                potential_changes += int(evidence['potential_change'] is not None)
                playstyle_changes += len(evidence['playstyle_changes'])
                # Native FC27 attribute/potential changes are observed only. Academy Engine
                # no longer owns attribute maturation/ageing or Dynamic Potential. Attribute
                # deltas are still valid evidence for PlayStyle/Role development while the
                # player is attached to a club. Free agents/missing players never accumulate
                # Academy Engine progression.
                development_window_active=(old_lifecycle=='CLUB' and lifecycle=='CLUB' and not offline_rebase and progression_trigger)
                if development_window_active:
                    psdev=update_playstyle_evidence(existing,evidence,checkpoint_id=checkpoint_id,career_date=(career_meta or {}).get('date') if isinstance(career_meta,dict) else None,training_days=training_days)
                    playstyle_progress_events += psdev['progress_events']; playstyle_ready += len(psdev['normal_ready']); playstyle_plus_ready += len(psdev['plus_ready'])
                if evidence['attribute_changes'] or evidence['potential_change'] is not None or evidence['playstyle_changes']:
                    existing.setdefault('history',[]).append({'type':'FC27_NATIVE_EVOLUTION','checkpoint_id':checkpoint_id,**evidence})
                if development_window_active:
                    tracked={'game':existing.get('game',{}),'engine':existing.setdefault('engine',{}),'history':existing.setdefault('history',[])}
                    tracked['engine'].setdefault('football_dna',existing.get('dna',{}))
                    evolved,receipt=ingest_checkpoint(tracked,snap,checkpoint_id=checkpoint_id,career_date=(career_meta or {}).get('date') if isinstance(career_meta,dict) else None)
                    existing['game']=evolved['game']; existing['engine']=evolved['engine']; existing['history']=evolved['history']
                    role_signals += len(receipt.get('role_training_signals',{}))
                restored_progress=_restore_progress_floor(existing.setdefault('engine',{}),progress_before)
                if restored_progress:
                    existing.setdefault('history',[]).append({'type':'PROGRESSION_FLOOR_RESTORED','checkpoint_id':checkpoint_id,'entries':[{'ledger':a,'key':b,'from':c,'to':d} for a,b,c,d in restored_progress]})
                if old_lifecycle and old_lifecycle!=lifecycle:
                    transitions+=1
                    existing['history'].append({'type':'LIFECYCLE_TRANSITION','checkpoint_id':checkpoint_id,'from':old_lifecycle,'to':lifecycle})
            existing['lifecycle']=lifecycle
            existing['clubteamid']=snap.get('clubteamid')
            # Preserve best-known display metadata when a transient snapshot falls
            # back to placeholder names or temporarily lacks localization.
            old_game=dict(existing.get('game') or {})
            merged_game=dict(snap)
            incoming_name=str(merged_game.get('name') or '')
            old_name=str(old_game.get('name') or '')
            if (not incoming_name or incoming_name.startswith('Generated Player #')) and old_name and not old_name.startswith('Generated Player #'):
                merged_game['name']=old_name
            if not str(merged_game.get('clubname') or '').strip() and str(old_game.get('clubname') or '').strip():
                merged_game['clubname']=old_game.get('clubname')
            existing['game']=merged_game
            age=snap.get('age')
            if isinstance(age,(int,float)):
                ah=existing.setdefault('history',[])
                last_age=next((h.get('age') for h in reversed(ah) if h.get('type')=='AGE_CHECKPOINT'),None)
                if last_age is None or int(last_age)!=int(age):
                    ah.append({'type':'AGE_CHECKPOINT','checkpoint_id':checkpoint_id,'age':int(age)})
            existing['last_checkpoint_id']=checkpoint_id
            existing['observed_this_checkpoint']=True
            # v1.24.36: seen again, so not retired (a record FC27 still holds).
            if existing.pop('retired',None) is not None:
                existing.setdefault('history',[]).append({'type':'RETIREMENT_CLEARED','checkpoint_id':checkpoint_id})
                # His face went back into the pool while he was away; an automatic one is
                # chosen again so he cannot share a face with a newer player.
                _f=(existing.get('engine') or {}).get('face')
                if isinstance(_f,dict) and _f.get('source')!='user': existing['engine'].pop('face',None)
            existing['missing_checkpoints']=0; existing.pop('missing_since_ordinal',None)
            if isinstance(snap.get('age'),(int,float)): existing['last_seen_age']=int(snap.get('age'))
            hist=existing.setdefault('history',[])
            # Keep enough evidence for a season while bounding file growth.
            if len(hist)>96: del hist[:-96]
        for key,p in data['players'].items():
            if key not in seen:
                p['observed_this_checkpoint']=False
                p['generation_new_this_checkpoint']=False

        # Season/lifecycle marker. A large generated cohort is the reliable signal we
        # have already validated at FC27 season rollover. Record it once so restarts and
        # save/reload do not manufacture additional season epochs.
        generation_cohort=new+replaced_generation
        if generation_cohort>=100 and data.get('last_season_boundary_checkpoint')!=checkpoint_id:
            data['season_epoch']=int(data.get('season_epoch',0) or 0)+1
            data['last_season_boundary_checkpoint']=checkpoint_id
            events=data.setdefault('season_events',[])
            events.append({'type':'SEASON_BOUNDARY_GENERATION_COHORT','checkpoint_id':checkpoint_id,'season_epoch':data['season_epoch'],'generation_cohort':generation_cohort})
            if len(events)>16: del events[:-16]
        # v1.24.36: retirement. FC27 removes a retired player's record, so an older player
        # missing from several consecutive full snapshots is treated as retired and hidden.
        # A snapshot much smaller than the previous one is not trusted for this.
        retirement=update_retirements(data,seen,previously_observed,checkpoint_id,career_meta); self.last_retirement=retirement
        # v1.24.36: PlayStyle decline with age (off by default). Progress is credited only
        # on the same continuous timeline that credits development.
        try:
            from .playstyle_decline import update_world as _decline_update
            from .runtime_config import decline as _decline_settings
            self.last_decline_result=_decline_update(data,credit=bool(progression_trigger and not offline_rebase),days=training_days,
                                                     settings=_decline_settings(),checkpoint_id=checkpoint_id)
        except Exception as exc:
            self.last_decline_result={'error':str(exc)}
        data['last_checkpoint_id']=checkpoint_id
        if offline_rebase:
            data['last_offline_rebase_checkpoint']=checkpoint_id
            data['offline_rebase_count']=int(data.get('offline_rebase_count',0) or 0)+1
        if request_id:
            processed.append(str(request_id)); del processed[:-128]
        incoming=len(players); observed=len(seen); missing=sum(1 for p in data['players'].values() if not p.get('observed_this_checkpoint',False))
        reconciled=(incoming==observed==club+free+other and len(data['players'])==observed+missing)
        # v1.24.31: faces from the user's regen-face library (off by default). A face
        # problem must never block a checkpoint, so failures are only recorded.
        # v1.24.32: faces picked in the overlay wait in face_choices.json beside the world
        # file and are moved into the world here, then cleared once the world is saved.
        choices_path=path.parent/'face_choices.json'
        try:
            from .faces import assign_faces, load_choices
            self.last_face_result=assign_faces(data,choices=load_choices(choices_path))
        except Exception as exc:
            self.last_face_result={'enabled':None,'error':str(exc)}
        _atomic(path,data)
        try:
            from .faces import clear_choices
            clear_choices(choices_path,(self.last_face_result or {}).get('applied_choices') or ())
        except Exception:
            pass
        # Keep the just-written world in memory so the caller does not re-parse it.
        self.last_world=data
        self.last_native_role_upgrades=native_upgrades
        return {'status':'OK' if reconciled else 'HOLD','native_role_upgrades':native_upgrades,'incoming':incoming,'observed':observed,'new':new,'returning':returning,'missing':missing,'tracked':len(data['players']),'club':club,'free_agent':free,'other':other,
                'replaced_generation':replaced_generation,'generation_cohort':generation_cohort,'season_epoch':int(data.get('season_epoch',0) or 0),'transitions':transitions,'role_signals':role_signals,'attribute_changes':attribute_changes,'potential_changes':potential_changes,'playstyle_changes':playstyle_changes,'playstyle_progress_events':playstyle_progress_events,'playstyle_ready':playstyle_ready,'playstyle_plus_ready':playstyle_plus_ready,'offline_rebase':offline_rebase,'elapsed_days':elapsed_days,'development_credited':progression_trigger,'training_days':training_days,'reconciled':reconciled,'path':str(path)}
