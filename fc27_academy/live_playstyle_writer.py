"""Integrated evolution production transaction coordinator.

Production families bundled here:
- normal PlayStyle acquisition (outfield + GK)
- PlayStyle+ acquisition (outfield + GK)
- verified Role+ -> Role++ upgrades
- queued newgen starting-PlayStyle enrichment

FC27 remains the sole owner of Dynamic Potential and attribute maturation/ageing.

The resident Lua consumer applies a whole changeset atomically: every expected value
must match, every write must read back, and any failure rolls back all already-applied
changes. Python state/cooldowns are mutated only after a durable APPLIED/COMMITTED
receipt. Failed/stale transactions are recorded and re-evaluated on a later checkpoint.
"""
from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from pathlib import Path
from dataclasses import replace
import json, os, time, uuid
from .staged_sync import Change, make_changeset, validate_change
from .playstyle_sync import verified_mapping
from .save_context import save_root
from .world_bootstrap_store import WorldBootstrapStore
from .playstyle_lifetime import normal_addition_slots, plus_addition_slots, ensure_policy, normal_cap, ABSOLUTE_NORMAL_CAP
from .playstyle_development_planner import current_styles
from .runtime_config import (normal_cooldown_days, plus_cooldown_days, role_cooldown_days, newgen_per_checkpoint,
    max_total_changes_per_checkpoint, max_normal_per_checkpoint, max_plus_per_checkpoint, max_role_transactions_per_checkpoint, prioritize_user_team_processing)
from .paths import ACADEMY_STATE_ROOT
from .transaction_index import note_manifest, pending_manifests, index_for

NORMAL_COOLDOWN_DAYS=120
PLUS_COOLDOWN_DAYS=180
MAX_TOTAL_CHANGES=12
MAX_NORMAL_PER_CHECKPOINT=6
MAX_PLUS_PER_CHECKPOINT=3
MAX_ROLE_TRANSACTIONS_PER_CHECKPOINT=3
MAX_NEWGEN_PER_CHECKPOINT=4
ROLE_COOLDOWN_DAYS=120


def _lua_string(value: str) -> str:
    return json.dumps(str(value)).replace("\\/", "/")


def render_pending_transaction(cs, *, career_uid: str | None = None, branch_id: str | None = None, storage_key: str | None = None, runtime_session: str | None = None, branch_guards: list[dict] | None = None) -> str:
    """Render the production transaction consumed by the resident Lua adapter.

    v1.24 production transactions are always persistent writes. The old test-only
    restore-after-success control path was removed from the shipping engine.
    """
    rows = [
        '{pid=%d,field=%s,expected=%d,target=%d}' %
        (c.player_id, _lua_string(c.field), c.expected, c.target)
        for c in cs.changes
    ]
    guards = [
        '{pid=%d,birthdate=%d,nationality=%d,overallrating=%d}' %
        (int(g['pid']), int(g['birthdate']), int(g['nationality']), int(g['overallrating']))
        for g in (branch_guards or [])
    ]
    return (
        'return {schema=2,changeset_id=%s,save_uid=%s,career_uid=%s,branch_id=%s,'
        'storage_key=%s,runtime_session=%s,restore_after_success=false,branch_guards={%s},changes={%s}}\n'
        % (
            _lua_string(cs.changeset_id), _lua_string(cs.save_uid),
            _lua_string(career_uid or cs.save_uid), _lua_string(branch_id or ''),
            _lua_string(storage_key or cs.save_uid), _lua_string(runtime_session or ''),
            ','.join(guards), ','.join(rows),
        )
    )


def _atomic_text(path:Path,text:str):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(text,encoding='utf-8'); replace_retry(tmp,path)

def _atomic_json(path:Path,obj):
    _atomic_text(path,json.dumps(obj,indent=2,sort_keys=True))
    note_manifest(path,obj)

def _json(path:Path, default=None):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return default

def _failure_log(root:Path, row:dict):
    uid=str(row.get('save_uid') or 'UNKNOWN_SAVE')
    p=save_root(root,uid)/'production_failures.jsonl'; p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as f:
        f.write(json.dumps({'ts':int(time.time()),**row},sort_keys=True)+'\n')

def _queue_path(root:Path, save_uid:str)->Path:
    return save_root(Path(root),save_uid)/'playstyle_enrichment_queue.json'

def _load_queue(root:Path,save_uid:str):
    return _json(_queue_path(root,save_uid),{'schema':1,'save_uid':str(save_uid),'items':[]})

def _save_queue(root:Path,save_uid:str,q):
    _atomic_json(_queue_path(root,save_uid),q)

def enqueue_newgen(root, world, enrichment):
    """Persist current newgen proposals so they can drain over later checkpoints."""
    root=Path(root); save_uid=str(world.get('save_uid')); q=_load_queue(root,save_uid)
    items=q.setdefault('items',[])
    # v1.24.24: one starting plan per player. A player is only "new" again when the
    # engine finds him afresh (reload after quitting without saving, a rewind, deleted
    # engine data). The queue is not rolled back with the save, so his previous,
    # unwritten plan is superseded instead of being stacked with the new one.
    proposals=enrichment.get('proposals') or []
    cohort={int(x) for x in (enrichment.get('cohort_playerids') or [])} | {int(p.get('playerid',0)) for p in proposals}
    planned={(int(p.get('playerid',0)),str(p.get('style'))) for p in proposals if p.get('validation')=='READY_NEWGEN_VERIFIED'}
    superseded=0
    for x in items:
        if x.get('status')!='QUEUED': continue
        k=(int(x.get('playerid',0)),str(x.get('style')))
        if k[0] in cohort and k not in planned:
            x.update(status='SUPERSEDED_REPLANNED',last_error='PLAYER_FOUND_AGAIN'); superseded+=1
    by_key={(int(x.get('playerid',0)),str(x.get('style'))):x for x in items if x.get('status') in ('QUEUED','STAGED')}
    added=0
    for p in proposals:
        if p.get('validation')!='READY_NEWGEN_VERIFIED': continue
        key=(int(p.get('playerid',0)),str(p.get('style')))
        if key in by_key: continue
        row={k:p.get(k) for k in ('playerid','style','field','bit','expected','proposed','birthdate','nationality','mapping_evidence','ovr','potential')}
        row.update(status='QUEUED',queue_id='ng_'+uuid.uuid4().hex,attempts=0,last_error=None)
        items.append(row); by_key[key]=row; added+=1
    _save_queue(root,save_uid,q)
    return {'queued_total':sum(x.get('status')=='QUEUED' for x in items),'added':added,'superseded':superseded}

def _world_player(world,pid):
    return (world.get('players') or {}).get(str(int(pid)))

def _prepare_queue_candidates(root,world):
    save_uid=str(world.get('save_uid')); q=_load_queue(root,save_uid); changed=False; ready=[]; holds=[]; reserved_by_player={}
    for item in q.get('items',[]):
        if item.get('status')!='QUEUED': continue
        p=_world_player(world,item.get('playerid',0))
        if not p or not p.get('observed_this_checkpoint',False):
            holds.append({'queue_id':item.get('queue_id'),'reason':'PLAYER_NOT_OBSERVED'}); continue
        g=p.get('game') or {}
        # Prevent a queued enrichment from ever crossing into a regenerated identity.
        if item.get('birthdate') is not None and g.get('birthdate') is not None and item.get('birthdate')!=g.get('birthdate'):
            item.update(status='CANCELLED_IDENTITY_REPLACED',last_error='BIRTHDATE_MISMATCH'); changed=True; continue
        if item.get('nationality') is not None and g.get('nationality') is not None and item.get('nationality')!=g.get('nationality'):
            item.update(status='CANCELLED_IDENTITY_REPLACED',last_error='NATIONALITY_MISMATCH'); changed=True; continue
        field=str(item.get('field')); bit=int(item.get('bit') or 0); cur=int(g.get(field,0) or 0)
        if bit<=0 or verified_mapping(field,bit) is None:
            item.update(status='HOLD_MAPPING',last_error='MAPPING_NOT_VERIFIED'); changed=True; continue
        if cur & bit:
            # FC27/native/another branch already owns it; resolve queue without a write.
            item.update(status='COMMITTED_EXTERNAL',expected=cur,proposed=cur,last_error=None); changed=True; continue
        ensure_policy(p)
        normal,_,_=current_styles(g); cap=min(ABSOLUTE_NORMAL_CAP,normal_cap(p))
        reserved=reserved_by_player.get(int(item.get('playerid',0)),0)
        if len(normal)+reserved >= cap or len(normal)+reserved >= ABSOLUTE_NORMAL_CAP:
            item.update(status='CANCELLED_LIFETIME_CAP',last_error='NORMAL_PLAYSTYLE_LIFETIME_CAP'); changed=True
            holds.append({'queue_id':item.get('queue_id'),'playerid':int(item.get('playerid',0)),'reason':'LIFETIME_PLAYSTYLE_CAP','normal_count':len(normal),'reserved':reserved,'personal_cap':cap,'absolute_cap':ABSOLUTE_NORMAL_CAP})
            continue
        reserved_by_player[int(item.get('playerid',0))]=reserved+1
        # Rebase expected value to the live checkpoint rather than retrying stale state.
        item['expected']=cur; item['proposed']=cur|bit; changed=True
        ready.append(item)
    if changed:_save_queue(root,save_uid,q)
    ready.sort(key=lambda x:(int(x.get('playerid',0)),str(x.get('style'))))
    return q,ready,holds

def _candidate_entry(x,kind,family,cooldown_days=0,queue_id=None):
    return {
        'kind':kind,'family':family,'playerid':int(x['playerid']),'style':str(x['style']),
        'field':str(x['field']),'bit':int(x['bit']),'expected':int(x['expected']),'proposed':int(x['proposed']),
        'progress_before':float(x.get('progress',0.0) or 0.0),'cooldown_days':int(cooldown_days),
        'mapping_evidence':x.get('mapping_evidence'),'queue_id':queue_id,
    }

def _safe_change(entry):
    c=Change(entry['playerid'],entry['field'],entry['expected'],entry['proposed'],entry['family'],f"{entry['kind']}:{entry['style']}")
    validate_change(c)
    return c

def _recover_orphaned_transactions(root:Path, save_uid:str):
    """Recover STAGED manifests left without a pending transaction or receipt.

    This covers a Python-side crash between manifest/queue durability and pending
    handoff creation. We never abort when either receipt location exists, because
    the resident Lua may already have consumed the transaction.
    """
    sr=save_root(root,save_uid)
    d=sr/'live_ps_transactions'; recovered=[]
    if not d.exists(): return recovered
    pending=sr/'pending_sync.lua'
    for mp,m in pending_manifests(root,d):
        if m.get('status') not in ('STAGED','STAGED_STATE_HOLD'): continue
        cid=str(m.get('changeset_id',''))
        if pending.exists(): continue
        if (sr/'sync_receipts'/f'{cid}.receipt.json').exists(): continue
        if (sr/'lua_receipts'/f'{cid}.receipt.json').exists(): continue
        _restore_queue_after_failure(root,m,'ORPHANED_BEFORE_RESIDENT_HANDOFF')
        m.update(status='ABORTED_ORPHAN',receipt_status='NONE',receipt_reason='ORPHANED_BEFORE_RESIDENT_HANDOFF')
        _atomic_json(mp,m); recovered.append(cid)
    return recovered

def stage_bundle(root,world,normal_acquisition,plus_acquisition,newgen_enrichment,role_acquisition=None,*,checkpoint_id):
    normal_cd=normal_cooldown_days(); plus_cd=plus_cooldown_days(); role_cd=role_cooldown_days(); max_newgen=newgen_per_checkpoint()
    max_total=max_total_changes_per_checkpoint(); max_normal=max_normal_per_checkpoint(); max_plus=max_plus_per_checkpoint(); max_role=max_role_transactions_per_checkpoint()
    root=Path(root); save_uid=str(world.get('save_uid')); sr=save_root(root,save_uid); sr.mkdir(parents=True,exist_ok=True); (sr/'lua_receipts').mkdir(parents=True,exist_ok=True)
    pending=sr/'pending_sync.lua'; manifests=sr/'live_ps_transactions'; manifests.mkdir(parents=True,exist_ok=True)
    recovered=_recover_orphaned_transactions(root,save_uid)
    qmeta=enqueue_newgen(root,world,newgen_enrichment)
    if pending.exists(): return {'status':'HOLD_PENDING_EXISTS','staged':0,'queue':qmeta}
    # Never issue two production changesets for one save/checkpoint.
    index=index_for(root)
    for uid,checkpoint,cid in index.checkpoints.values():
        if uid==save_uid and checkpoint==str(checkpoint_id):
            return {'status':'HOLD_CHECKPOINT_ALREADY_USED','staged':0,'changeset_id':cid,'queue':qmeta}
    for _,obj in pending_manifests(root,manifests):
        return {'status':'HOLD_UNRESOLVED_TRANSACTION','staged':0,'changeset_id':obj.get('changeset_id'),'queue':qmeta}

    entries=[]; holds=[]
    prefer_user=prioritize_user_team_processing(); user_teamid=(world.get('career') or {}).get('user_teamid')
    def _user_priority(pid):
        if not prefer_user or user_teamid in (None,'',0,'0'): return 1
        wp=_world_player(world,pid) or {}; g=wp.get('game') or {}
        return 0 if g.get('clubteamid')==user_teamid else 1
    def add_candidates(rows,kind,family,limit,cooldown):
        for x in sorted(rows,key=lambda r:(_user_priority(r.get('playerid',0)),int(r.get('playerid',0)),str(r.get('style','')))):
            if limit<=0: break
            expected_validation='READY_CONTROLLED_VERIFIED' if kind=='NORMAL_ACQUISITION' else 'READY_PLUS_VERIFIED'
            if x.get('validation')!=expected_validation: continue
            wp=_world_player(world,x.get('playerid',0))
            if not wp:
                holds.append({'kind':kind,'playerid':int(x.get('playerid',0)),'style':str(x.get('style')),'reason':'PLAYER_NOT_IN_WORLD'}); continue
            ensure_policy(wp)
            if kind=='NORMAL_ACQUISITION' and normal_addition_slots(wp)<=0:
                holds.append({'kind':kind,'playerid':int(x.get('playerid',0)),'style':str(x.get('style')),'reason':'LIFETIME_PLAYSTYLE_CAP'}); continue
            if kind=='PLUS_ACQUISITION' and plus_addition_slots(wp)<=0:
                holds.append({'kind':kind,'playerid':int(x.get('playerid',0)),'style':str(x.get('style')),'reason':'PLUS_LIFETIME_ELIGIBILITY'}); continue
            e=_candidate_entry(x,kind,family,cooldown)
            key=(e['playerid'],e['field'])
            try:_safe_change(e)
            except Exception as exc:
                holds.append({'kind':kind,'playerid':e['playerid'],'style':e['style'],'reason':'VALIDATION_ERROR','error':str(exc)}); continue
            entries.append(e)
    add_candidates(normal_acquisition.get('verified_candidates') or [],'NORMAL_ACQUISITION','PLAYSTYLE',max_normal,normal_cd)
    add_candidates(plus_acquisition.get('verified_candidates') or [],'PLUS_ACQUISITION','PLAYSTYLE_PLUS',max_plus,plus_cd)

    # Role production: bounded semantic Role transactions per checkpoint. A semantic
    # Role can exist in multiple role fields for different positions; all matching
    # fields are written atomically in the same resident changeset.
    role_candidates=sorted(((role_acquisition or {}).get('verified_candidates') or []),key=lambda r:(_user_priority(r.get('playerid',0)),-float(r.get('progress',0) or 0),int(r.get('playerid',0)),str(r.get('role',''))))
    for rc in role_candidates:
        if max_role<=0: break
        pid=int(rc.get('playerid',0)); role=str(rc.get('role',''))
        field_changes=list(rc.get('field_changes') or [])
        if not field_changes:
            holds.append({'kind':'ROLE_UPGRADE','playerid':pid,'role':role,'reason':'NO_ROLE_FIELDS'}); continue
        if len(field_changes)>max_total:
            holds.append({'kind':'ROLE_UPGRADE','playerid':pid,'role':role,'reason':'BUNDLE_FIELD_LIMIT'}); continue
        staged_role=[]; role_error=None
        for fc in field_changes:
            e={'kind':'ROLE_UPGRADE','family':'ROLE','playerid':pid,'role':role,'style':role,'field':str(fc['field']),
               'bit':0,'expected':int(fc['expected']),'proposed':int(fc['proposed']),'progress_before':float(rc.get('progress',0) or 0),
               'cooldown_days':role_cd,'mapping_evidence':rc.get('mapping_evidence'),'queue_id':None}
            key=(pid,e['field'])
            try:_safe_change(e)
            except Exception as exc:
                role_error='VALIDATION_ERROR:'+str(exc); break
            staged_role.append(e)
        if role_error:
            holds.append({'kind':'ROLE_UPGRADE','playerid':pid,'role':role,'reason':role_error}); continue
        entries.extend(staged_role)

    # v1.24.36: PlayStyle decline. A ready loss (or PlayStyle+ downgrade) is one atomic group.
    from .playstyle_decline import loss_entries, DECLINE_WRITES_PER_CHECKPOINT
    from .runtime_config import decline as _decline_cfg
    _dcfg=_decline_cfg()
    _switch={'LOSS':bool(_dcfg.get('playstyle_loss_enabled')),'PLUS_DOWNGRADE':bool(_dcfg.get('playstyle_plus_loss_enabled'))}
    for _pid,_p in sorted((world.get('players') or {}).items(),key=lambda kv:(_user_priority(int(kv[0])),int(kv[0]))):
        ready=((_p.get('engine') or {}).get('decline') or {}).get('ready')
        if not ready or not _p.get('observed_this_checkpoint',False) or _p.get('retired'): continue
        if not _switch.get(str(ready.get('kind'))): continue          # switched off since it became ready: never written
        group,why=loss_entries(_p,ready)
        if why:
            holds.append({'kind':'PLAYSTYLE_DECLINE','playerid':int(_pid),'style':ready.get('style'),'reason':why}); continue
        try:
            for e in group: _safe_change(e)
        except Exception as exc:
            holds.append({'kind':'PLAYSTYLE_DECLINE','playerid':int(_pid),'style':ready.get('style'),'reason':'VALIDATION_ERROR','error':str(exc)}); continue
        entries.extend(group)

    q,qready,qholds=_prepare_queue_candidates(root,world); holds.extend(qholds)
    # Group all queued starting PlayStyles for one newgen/player field into
    # one exact additive bitfield write. This lets a newly scouted/generated player
    # receive a 2/3/4/5-PlayStyle starting profile atomically instead of requiring one
    # save per style. The configured shared field ceiling still applies.
    grouped={}
    for item in qready:
        key=(int(item.get('playerid',0)),str(item.get('field')))
        grouped.setdefault(key,[]).append(item)
    for (pid,field),items in sorted(grouped.items(),key=lambda kv:(_user_priority(kv[0][0]),kv[0][0],kv[0][1])):
        if max_newgen<=0: break
        key=(pid,field)
        expected=int(items[0].get('expected',0) or 0); bitmask=0; styles=[]; qids=[]; evidences=[]
        for item in items:
            # _prepare_queue_candidates rebases every item against the same live field.
            if int(item.get('expected',0) or 0)!=expected: continue
            bit=int(item.get('bit') or 0)
            if bit<=0 or (expected & bit): continue
            bitmask |= bit; styles.append(str(item.get('style'))); qids.append(item.get('queue_id')); evidences.append(item.get('mapping_evidence'))
        if not bitmask: continue
        e={'kind':'NEWGEN_ENRICHMENT','family':'PLAYSTYLE_SET','playerid':pid,'style':' + '.join(styles),'styles':styles,
           'field':field,'bit':bitmask,'expected':expected,'proposed':expected|bitmask,'progress_before':0.0,'cooldown_days':0,
           'mapping_evidence':'FC27_VERIFIED_MULTI_BIT_SET','queue_id':qids[0] if len(qids)==1 else None,'queue_ids':qids}
        try:_safe_change(e)
        except Exception as exc:
            holds.append({'kind':'NEWGEN_ENRICHMENT','playerid':pid,'styles':styles,'reason':'VALIDATION_ERROR','error':str(exc)}); continue
        entries.append(e)

    from .production_scheduler import select_groups
    scheduler_path=sr/'production_scheduler.json'
    scheduler=_json(scheduler_path,{}) or {}
    entries,scheduler,schedule_holds=select_groups(entries,max_total,
        {'NORMAL_ACQUISITION':max_normal,'PLUS_ACQUISITION':max_plus,'ROLE_UPGRADE':max_role,'NEWGEN_ENRICHMENT':max_newgen,
         'PLAYSTYLE_LOSS':DECLINE_WRITES_PER_CHECKPOINT,'PLUS_DOWNGRADE':DECLINE_WRITES_PER_CHECKPOINT},
        scheduler,user_priority=_user_priority)
    holds.extend(schedule_holds)

    if not entries:
        return {'status':'HOLD_NO_PRODUCTION_CANDIDATE','staged':0,'queue':qmeta,'holds':holds,
                'normal_available':len(normal_acquisition.get('verified_candidates') or []),'plus_available':len(plus_acquisition.get('verified_candidates') or []),'recovered_orphans':recovered}

    changes=tuple(_safe_change(e) for e in entries)
    cid='evobundle_'+uuid.uuid4().hex
    cs=make_changeset(save_uid,str(checkpoint_id),changes,mode='APPLY_VERIFIED'); cs=replace(cs,changeset_id=cid)
    manifest={'schema':6,'version':'1.0.7','changeset_id':cid,'save_uid':save_uid,'career_uid':str(world.get('career_uid') or save_uid),'branch_id':str(world.get('branch_id') or ''),'storage_key':str(world.get('storage_key') or save_uid),'runtime_session':str(world.get('runtime_session') or ''),'checkpoint_id':str(checkpoint_id),'status':'STAGED','entries':entries,'holds':holds,'limits':{'total_fields':max_total,'normal':max_normal,'plus':max_plus,'role_transactions':max_role,'newgen':max_newgen}}
    _atomic_json(manifests/f'{cid}.json',manifest)
    # Mark queued newgen rows STAGED only after manifest is durable.
    if any(e.get('queue_id') or e.get('queue_ids') for e in entries):
        q=_load_queue(root,save_uid); ids=set(); [ids.update(e.get('queue_ids') or ([e.get('queue_id')] if e.get('queue_id') else [])) for e in entries]
        for item in q.get('items',[]):
            if item.get('queue_id') in ids:
                item['status']='STAGED'; item['changeset_id']=cid; item['attempts']=int(item.get('attempts',0) or 0)+1
        _save_queue(root,save_uid,q)
    guards=[]
    target_ids={e['playerid'] for e in entries}
    for _pid,_p in sorted((world.get('players') or {}).items(), key=lambda kv:int(kv[0])):
        _g=_p.get('game') or {}
        if int(_pid) not in target_ids: continue
        if not _p.get('observed_this_checkpoint',False): continue
        if all(isinstance(_g.get(k),(int,float)) for k in ('birthdate','nationality','overallrating')):
            guards.append({'pid':int(_pid),'birthdate':int(_g['birthdate']),'nationality':int(_g['nationality']),'overallrating':int(_g['overallrating'])})

    manifest['branch_guards']=guards; _atomic_json(manifests/f'{cid}.json',manifest)
    _atomic_text(pending,render_pending_transaction(cs,career_uid=str(world.get('career_uid') or save_uid),branch_id=str(world.get('branch_id') or ''),storage_key=str(world.get('storage_key') or save_uid),runtime_session=str(world.get('runtime_session') or ''),branch_guards=guards))
    _atomic_json(scheduler_path,scheduler)
    kinds={k:sum(e['kind']==k for e in entries) for k in ('NORMAL_ACQUISITION','PLUS_ACQUISITION','ROLE_UPGRADE','NEWGEN_ENRICHMENT','PLAYSTYLE_LOSS','PLUS_DOWNGRADE')}
    role_transactions=len({(e['playerid'],e.get('role')) for e in entries if e['kind']=='ROLE_UPGRADE'})
    return {'status':'STAGED_EVOLUTION_BUNDLE','staged':len(entries),'changeset_id':cid,'entries':entries,'kinds':kinds,'role_transactions':role_transactions,'queue':qmeta,'holds':holds,'recovered_orphans':recovered}



def _restore_queue_after_failure(root:Path,m,reason):
    save_uid=str(m.get('save_uid')); q=_load_queue(root,save_uid); ids=set(); [ids.update(e.get('queue_ids') or ([e.get('queue_id')] if e.get('queue_id') else [])) for e in m.get('entries',[])]
    changed=False
    for item in q.get('items',[]):
        if item.get('queue_id') in ids and item.get('status')=='STAGED':
            item['status']='QUEUED'; item['last_error']=str(reason); changed=True
    if changed:_save_queue(root,save_uid,q)

def apply_receipt(root,receipt):
    root=Path(root); cid=str(receipt.get('changeset_id',''))
    mp=index_for(root).by_id.get(cid)
    if mp is None: return {'handled':False,'status':'MANIFEST_NOT_FOUND'}
    if not mp.exists(): return {'handled':False}
    m=_json(mp,{}) or {}
    if m.get('status') not in ('STAGED','STAGED_STATE_HOLD'): return {'handled':True,'status':'IDEMPOTENT','changeset_id':cid}
    status=str(receipt.get('status')); reason=str(receipt.get('reason'))
    if status!='APPLIED' or reason!='COMMITTED':
        _restore_queue_after_failure(root,m,reason)
        m.update(status='FAILED',receipt_status=status,receipt_reason=reason); _atomic_json(mp,m)
        _failure_log(root,{'save_uid':m.get('save_uid'),'changeset_id':cid,'status':status,'reason':reason,'entries':m.get('entries',[])})
        return {'handled':True,'status':'FAILED','changeset_id':cid,'receipt_status':status,'reason':reason}
    wp=WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(str(m['save_uid']))
    if not wp.exists():
        m.update(status='STAGED_STATE_HOLD',state_hold='WORLD_MISSING',receipt_status=status,receipt_reason=reason); _atomic_json(mp,m)
        _failure_log(root,{'save_uid':m.get('save_uid'),'changeset_id':cid,'status':'HOLD_WORLD_MISSING'})
        return {'handled':True,'status':'HOLD_WORLD_MISSING','changeset_id':cid}
    world=_json(wp,{}) or {}; committed=[]
    # Validate all state targets first; do not partially mutate Python state after a
    # fully committed FC27 transaction.
    for e in m.get('entries',[]):
        p=(world.get('players') or {}).get(str(e['playerid']))
        if not p:
            m.update(status='STAGED_STATE_HOLD',state_hold='PLAYER_MISSING',missing_player=e['playerid'],receipt_status=status,receipt_reason=reason); _atomic_json(mp,m)
            _failure_log(root,{'save_uid':m.get('save_uid'),'changeset_id':cid,'status':'HOLD_PLAYER_MISSING','playerid':e['playerid']})
            return {'handled':True,'status':'HOLD_PLAYER_MISSING','changeset_id':cid,'playerid':e['playerid']}
    for e in m.get('entries',[]):
        p=(world.get('players') or {})[str(e['playerid'])]; eng=p.setdefault('engine',{})
        if e['kind']=='NORMAL_ACQUISITION':
            eng.setdefault('playstyle_progress',{})[e['style']]=0.0
            eng['playstyle_acquisition_cooldown_days_remaining']=int(e['cooldown_days'])
            eng['playstyle_acquisition_last_receipt']=cid
        elif e['kind']=='PLUS_ACQUISITION':
            eng.setdefault('playstyle_plus_progress',{})[e['style']]=0.0
            eng['playstyle_plus_cooldown_days_remaining']=int(e['cooldown_days'])
            eng['playstyle_plus_last_receipt']=cid
        elif e['kind']=='ROLE_UPGRADE':
            eng.setdefault('role_progress',{})[e['role']]=0.0
            eng['role_acquisition_cooldown_days_remaining']=int(e['cooldown_days'])
            eng['role_acquisition_last_receipt']=cid
        elif e['kind'] in ('PLAYSTYLE_LOSS','PLUS_DOWNGRADE') and e.get('family')!='PLAYSTYLE':
            # v1.24.36: once per loss (a downgrade's added normal bit is the same group).
            # A loss never touches acquisition or Role++ cooldowns.
            from .playstyle_decline import apply_committed_loss
            info=apply_committed_loss(p,'LOSS' if e['kind']=='PLAYSTYLE_LOSS' else 'PLUS_DOWNGRADE',str(e['style']),
                                      normal_before=int(e.get('normal_before',0) or 0),added_normal=bool(e.get('added_normal')),kept_normal=e.get('kept_normal'),
                                      career_date=(world.get('career') or {}).get('date'),changeset_id=cid)
            e['cap_before']=info.get('cap_before'); e['cap_after']=info.get('cap_after')
        # v1.24.12: reflect the committed FC27 value immediately so Player Details
        # matches the timeline without waiting for the next snapshot.
        try: p.setdefault('game',{})[str(e['field'])]=int(e['proposed'])
        except (KeyError,TypeError,ValueError): pass
        hist=p.setdefault('history',[])
        htype='ROLE_PRODUCTION_COMMIT' if e['kind']=='ROLE_UPGRADE' else 'PLAYSTYLE_PRODUCTION_COMMIT'
        hkey=e.get('role') if e['kind']=='ROLE_UPGRADE' else e.get('style')
        if not any(h.get('type')==htype and h.get('changeset_id')==cid and h.get('kind')==e['kind'] and (h.get('role') if e['kind']=='ROLE_UPGRADE' else h.get('style'))==hkey and h.get('field')==e.get('field') for h in hist):
            row={'type':htype,'changeset_id':cid,'kind':e['kind'],'field':e['field'],'expected':e['expected'],'proposed':e['proposed'],'career_date':dict((world.get('career') or {}).get('date') or {}),'created_at':int(time.time())}
            if e['kind']=='ROLE_UPGRADE': row['role']=e['role']
            else: row.update(style=e['style'],bit=e['bit'])
            hist.append(row)
        if e['kind'] in ('PLAYSTYLE_LOSS','PLUS_DOWNGRADE') and e.get('family')=='PLAYSTYLE': continue   # one event per downgrade
        committed.append({'playerid':e['playerid'],'style':e.get('style'),'role':e.get('role'),'field':e.get('field'),'kind':e['kind'],
                          'cap_before':e.get('cap_before'),'cap_after':e.get('cap_after'),'added_normal':e.get('added_normal')})
    _atomic_json(wp,world)
    # Resolve queued newgen items only after world bookkeeping is durable.
    q=_load_queue(root,str(m['save_uid'])); ids=set(); [ids.update(e.get('queue_ids') or ([e.get('queue_id')] if e.get('queue_id') else [])) for e in m.get('entries',[])]; changed=False
    for item in q.get('items',[]):
        if item.get('queue_id') in ids:
            item.update(status='COMMITTED',last_error=None,changeset_id=cid); changed=True
    if changed:_save_queue(root,str(m['save_uid']),q)
    m.update(status='COMMITTED',receipt_status=status,receipt_reason=reason,committed=committed); _atomic_json(mp,m)
    return {'handled':True,'status':'COMMITTED','changeset_id':cid,'storage_key':str(m.get('save_uid')),'committed_count':len(committed),'committed':committed}

def reconcile_durable_receipts(root):
    root=Path(root); out=[]
    saves=root/'saves'
    for mp,m in pending_manifests(root):
        if m.get('status') not in ('STAGED','STAGED_STATE_HOLD'): continue
        sr=save_root(root,str(m.get('save_uid')))
        rp=sr/'sync_receipts'/f"{m.get('changeset_id')}.receipt.json"
        if not rp.exists(): continue
        try:out.append(apply_receipt(root,_json(rp,{}) or {}))
        except Exception as e:
            _failure_log(root,{'save_uid':m.get('save_uid'),'changeset_id':m.get('changeset_id'),'status':'RECONCILE_ERROR','error':str(e)})
            out.append({'handled':True,'status':'RECONCILE_ERROR','changeset_id':m.get('changeset_id'),'error':str(e)})
    return out
