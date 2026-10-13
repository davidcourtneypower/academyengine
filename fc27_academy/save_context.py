from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from pathlib import Path
import json, os, shutil
from .save_restore_points import restore_for_date


def _safe(uid:str)->str:
    return ''.join(c for c in str(uid) if c.isalnum() or c in '-_') or 'UNKNOWN_SAVE'


def _atomic(path:Path,obj:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8')
    replace_retry(tmp,path)


def save_root(bridge_root:Path|str, storage_key:str)->Path:
    return Path(bridge_root)/'saves'/_safe(storage_key)


def _load(path:Path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return default


def identity_overlap(source_world:dict, incoming_players:list[dict])->tuple[int,int,float]:
    src=source_world.get('players') or {}
    matched=0; comparable=0
    for p in incoming_players:
        old=src.get(str(int(p.get('playerid',-1))))
        if not old: continue
        g=old.get('game') or {}
        if g.get('birthdate') is None or p.get('birthdate') is None: continue
        comparable += 1
        if g.get('birthdate')==p.get('birthdate') and g.get('nationality')==p.get('nationality'):
            matched += 1
    return matched,comparable,(matched/comparable if comparable else 0.0)


def _clone_storage(bridge_root:Path, state_root:Path, source_key:str, target_key:str):
    src_world=state_root/'saves'/_safe(source_key)/'generated_world.json'
    dst_world=state_root/'saves'/_safe(target_key)/'generated_world.json'
    if src_world.exists() and not dst_world.exists():
        dst_world.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src_world,dst_world)
    # Clone durable branch state/queues, but never in-flight transactions or receipts.
    src=save_root(bridge_root,source_key); dst=save_root(bridge_root,target_key)
    dst.mkdir(parents=True,exist_ok=True)
    for name in ('playstyle_enrichment_queue.json',):
        a=src/name; b=dst/name
        if a.exists() and not b.exists():
            queue=_load(a,{'items':[]}); queue['save_uid']=target_key
            for item in queue.get('items',[]):
                if item.get('status')=='STAGED':
                    item['status']='QUEUED'; item.pop('changeset_id',None)
            _atomic(b,queue)
    # Events are durable history of this forward branch, not in-flight work.
    source_events=state_root.parent/'events'/_safe(source_key)/'events.json'
    target_events=state_root.parent/'events'/_safe(target_key)/'events.json'
    if source_events.exists() and not target_events.exists():
        target_events.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source_events,target_events)
    inherit_settings(state_root,source_key,target_key)


def inherit_settings(state_root, source_key, target_key):
    # v1.24.22: settings belong to the career (all branches share one file); only a
    # different career (e.g. Save As to a new slot) inherits a copy, and never over
    # settings it already has.
    from .runtime_config import settings_file, settings_career_key
    if not source_key or not target_key or settings_career_key(source_key)==settings_career_key(target_key): return False
    settings_root=Path(state_root).parent/'career_settings'
    a=settings_file(settings_root,source_key); b=settings_file(settings_root,target_key)
    if a.exists() and not b.exists():
        b.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(a,b); return True
    return False


def ensure_save_context(bridge_root:Path|str, state_root:Path|str, *, save_uid:str, runtime_session:str|None, players:list[dict], store,
                        storage_key:str|None=None, branch_id:str|None=None, parent_storage_key:str|None=None,
                        rollback_from_storage_key:str|None=None,
                        rollback_date:dict|None=None)->dict:
    """Ensure one isolated storage namespace per resolved save branch.

    `save_uid` is the FC27 career/slot UID. `storage_key` is the Academy Engine branch
    namespace resolved from live-state fingerprints. The two are intentionally distinct.
    """
    bridge_root=Path(bridge_root); state_root=Path(state_root)
    uid=str(save_uid); key=str(storage_key or uid); target=store.path_for(key)
    result={'save_uid':uid,'career_uid':uid,'branch_id':branch_id,'storage_key':key,
            'state':'RESUMED_EXISTING' if target.exists() else 'INITIALISED_NEW_BRANCH','parent_storage_key':None,'identity_overlap':None,'rollback':None}

    # A backwards FC27 save load is not a normal parent clone: cloning the current
    # future world would preserve acquisitions/progress that the user explicitly
    # discarded by loading the older save. Restore a date-aligned Academy snapshot
    # when available; if no v1.24 checkpoint exists, re-baseline from the live game.
    if rollback_from_storage_key and str(rollback_from_storage_key)!=key and not target.exists():
        rb=restore_for_date(str(rollback_from_storage_key),key,rollback_date)
        result['rollback']=rb
        if rb.get('status')=='RESTORED':
            result['state']='RESTORED_REWIND_POINT'; result['parent_storage_key']=str(rollback_from_storage_key)
        else:
            result['state']='REBASED_REWIND_FROM_LIVE'
        # Settings are user policy, not simulated career state, so keep them across
        # a rewind branch even when no historical engine restore point exists.
        inherit_settings(state_root,str(rollback_from_storage_key),key)
        target=store.path_for(key)

    source_key=None
    if parent_storage_key and str(parent_storage_key)!=key:
        source_key=str(parent_storage_key)
        result['state']='BRANCHED_FROM_PARENT_STATE'

    if not target.exists() and source_key:
        src=store.path_for(source_key)
        if src.exists():
            sw=_load(src,{})
            matched,comparable,ratio=identity_overlap(sw,players)
            result['identity_overlap']=round(ratio,4)
            if comparable>=min(40,len(players),len(sw.get('players') or {})) and comparable>0 and ratio>=0.90:
                _clone_storage(bridge_root,state_root,source_key,key)
                result['parent_storage_key']=source_key
            else:
                result['state']='INITIALISED_NEW_BRANCH'

    # Persist only descriptive active-context metadata here. Branch matching itself is
    # owned by branch_identity.py and is not inferred from this file.
    ctx_path=state_root/'save_context.json'; ctx=_load(ctx_path,{'schema':2})
    ctx.update(schema=2,active_save_uid=uid,active_branch_id=branch_id,active_storage_key=key,
               runtime_session=str(runtime_session) if runtime_session is not None else None)
    _atomic(ctx_path,ctx)
    return result
