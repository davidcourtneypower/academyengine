from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from pathlib import Path
import hashlib, json, os, statistics, time

SCHEMA=1
SAMPLE_LIMIT=1024


def _safe(v:str)->str:
    return ''.join(c for c in str(v) if c.isalnum() or c in '-_') or 'UNKNOWN'


def _atomic(path:Path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8')
    replace_retry(tmp,path)


def _load(path:Path, default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return default


def registry_path(root:Path|str, career_uid:str)->Path:
    return Path(root)/'branch_registry'/f'{_safe(career_uid)}.json'


def branch_storage_key(career_uid:str, branch_id:str)->str:
    return f'{_safe(career_uid)}__branch__{_safe(branch_id)}'


def _sample(players:list[dict])->dict[str,list[int]]:
    rows=[]
    for p in players:
        try:
            pid=int(p.get('playerid'))
        except Exception:
            continue
        bd=p.get('birthdate'); nat=p.get('nationality')
        if not isinstance(bd,(int,float)) or not isinstance(nat,(int,float)): continue
        age=p.get('age'); ovr=p.get('overallrating'); tid=p.get('clubteamid')
        rows.append((pid,int(bd),int(nat),int(age) if isinstance(age,(int,float)) else -1,int(ovr) if isinstance(ovr,(int,float)) else -1,int(tid) if isinstance(tid,(int,float)) else -1))
    # Stable hash-ranked sample. Adding a large newgen cohort must not reshuffle
    # most sampled IDs and make the same career look like a different branch.
    rows.sort(key=lambda x:(hashlib.sha256(str(x[0]).encode()).digest(), x[0]))
    if len(rows)>SAMPLE_LIMIT:
        rows=rows[:SAMPLE_LIMIT]
    rows.sort(key=lambda x:x[0])
    return {str(r[0]):list(r[1:]) for r in rows}


def make_signature(players:list[dict])->dict:
    s=_sample(players)
    immutable='|'.join(f'{pid}:{v[0]}:{v[1]}' for pid,v in sorted(s.items(),key=lambda kv:int(kv[0])))
    mutable='|'.join(f'{pid}:{v[2]}:{v[3]}:{v[4]}' for pid,v in sorted(s.items(),key=lambda kv:int(kv[0])))
    return {
        'count':len(players),'sample':s,
        'immutable_digest':hashlib.sha256(immutable.encode()).hexdigest()[:20],
        'state_digest':hashlib.sha256((immutable+'#'+mutable).encode()).hexdigest()[:20],
    }


def compare(a:dict|None,b:dict|None)->dict:
    if not a or not b:return {'comparable':0,'identity_overlap':0.0,'age_median_delta':99.0,'age_back_fraction':1.0,'ovr_mean_delta':99.0,'ovr_back_fraction':1.0,'count_ratio':0.0}
    sa=a.get('sample') or {}; sb=b.get('sample') or {}
    ages=[]; ovrs=[]; back=0; ovr_back=0; comparable=0; ident=0
    for pid,va in sa.items():
        vb=sb.get(pid)
        if not vb: continue
        comparable += 1
        if va[0]==vb[0] and va[1]==vb[1]:
            ident += 1
            aa,ab=va[2],vb[2]; oa,ob=va[3],vb[3]
            if aa>=0 and ab>=0:
                ages.append(abs(ab-aa)); back += int(ab<aa)
            if oa>=0 and ob>=0:
                ovrs.append(abs(ob-oa)); ovr_back += int(ob<oa)
    c1=max(1,int(a.get('count') or 0)); c2=max(1,int(b.get('count') or 0))
    return {
        'comparable':comparable,
        'identity_overlap':ident/comparable if comparable else 0.0,
        'age_median_delta':statistics.median(ages) if ages else 99.0,
        'age_back_fraction':back/len(ages) if ages else 1.0,
        'ovr_mean_delta':sum(ovrs)/len(ovrs) if ovrs else 99.0,
        'ovr_back_fraction':ovr_back/len(ovrs) if ovrs else 1.0,
        'count_ratio':min(c1,c2)/max(c1,c2),
    }


def _continuity(c:dict)->bool:
    return c['comparable']>=40 and c['identity_overlap']>=0.92 and c['age_back_fraction']<=0.01 and c['age_median_delta']<=1.25 and c['ovr_mean_delta']<=5.0 and not (c['ovr_back_fraction']>0.35 and c['ovr_mean_delta']>1.0) and c['count_ratio']>=0.55


def _branch_match(c:dict)->bool:
    return c['comparable']>=40 and c['identity_overlap']>=0.92 and c['age_median_delta']<=0.5 and c['ovr_mean_delta']<=4.0 and c['count_ratio']>=0.55


def _candidate_same(c:dict)->bool:
    return c['comparable']>=30 and c['identity_overlap']>=0.90 and c['age_median_delta']<=0.25 and c['ovr_mean_delta']<=2.5 and c['count_ratio']>=0.80


def _small_candidate_same(a:dict|None,b:dict|None)->bool:
    """Stabilise genuinely tiny, brand-new careers using immutable identity only.

    FC27 can expose only a handful of generated players in a fresh career. Mutable fields
    (age/OVR/team) may legitimately settle or change between consecutive day events, so
    they must not reset the confirmation counter. For tiny populations we require a stable
    immutable player identity set (playerid + birthdate + nationality).
    """
    if not a or not b: return False
    ca=int(a.get('count') or 0); cb=int(b.get('count') or 0)
    if ca <= 0 or cb <= 0 or ca >= 30 or cb >= 30: return False
    sa=a.get('sample') or {}; sb=b.get('sample') or {}
    if not sa or not sb: return False
    # Exact identity-set match is the normal tiny-career path.
    if set(sa) == set(sb):
        return all((sb.get(pid) and va[0]==sb[pid][0] and va[1]==sb[pid][1]) for pid,va in sa.items())
    # Allow one player to appear/disappear while FC27 finishes initialising, but only
    # when the overlapping immutable identities are all exact and represent >=75%.
    common=set(sa).intersection(sb)
    if not common: return False
    if len(common) / max(len(sa),len(sb)) < 0.75: return False
    if abs(ca-cb) > 1: return False
    return all(sa[pid][0]==sb[pid][0] and sa[pid][1]==sb[pid][1] for pid in common)


def _sparse_continuity(a:dict|None,b:dict|None)->bool:
    """Continuity for careers with fewer than 40 comparable generated players.

    Uses immutable identity overlap plus directional age/OVR checks. This lets a new
    career grow from 4 -> 5 -> ... generated players without manufacturing a new branch,
    while still treating backwards age/OVR movement as possible rewind evidence.
    """
    if not a or not b: return False
    sa=a.get('sample') or {}; sb=b.get('sample') or {}
    if not sa or not sb: return False
    if min(int(a.get('count') or 0), int(b.get('count') or 0)) >= 40: return False
    exact=[]
    for pid,va in sa.items():
        vb=sb.get(pid)
        if vb and va[0]==vb[0] and va[1]==vb[1]: exact.append((va,vb))
    smaller=max(1,min(len(sa),len(sb)))
    if len(exact) < max(1, int(smaller*0.75)): return False
    if len(exact)/smaller < 0.75: return False
    age_back=0; ovr_back=0; ovr_deltas=[]
    for va,vb in exact:
        if va[2]>=0 and vb[2]>=0 and vb[2] < va[2]: age_back += 1
        if va[3]>=0 and vb[3]>=0:
            if vb[3] < va[3]: ovr_back += 1
            ovr_deltas.append(abs(vb[3]-va[3]))
    if age_back: return False
    # A single one-point correction is tolerable while the career settles. Multiple
    # backwards OVR moves are treated as rewind evidence rather than forward continuity.
    if ovr_deltas and ovr_back/max(1,len(ovr_deltas)) > 0.25 and (sum(ovr_deltas)/len(ovr_deltas)) > 0.75:
        return False
    return True


def _new_branch_id(career_uid:str,sig:dict)->str:
    seed=f"{career_uid}|{sig.get('immutable_digest')}|{sig.get('state_digest')}|{sig.get('count')}"
    return 'b_'+hashlib.sha256(seed.encode()).hexdigest()[:12]


def write_active_context(root:Path|str, *, career_uid:str, branch_id:str|None=None, storage_key:str|None=None, runtime_session:str|None=None, writes_held:bool=False, reason:str='OK'):
    root=Path(root); p=root/'active_context.lua'; tmp=p.with_suffix('.lua.tmp')
    def q(v):return json.dumps(str(v or ''))
    text='return {schema=2,career_uid=%s,branch_id=%s,storage_key=%s,runtime_session=%s,writes_held=%s,reason=%s}\n'%(
        q(career_uid),q(branch_id),q(storage_key),q(runtime_session),'true' if writes_held else 'false',q(reason))
    tmp.write_text(text,encoding='utf-8'); replace_retry(tmp,p)
    return p


def _date_ordinal(d:dict|None):
    if not isinstance(d,dict): return None
    try:
        import datetime as _dt
        return _dt.date(int(d.get("year")),int(d.get("month")),int(d.get("day"))).toordinal()
    except Exception:
        return None


def resolve_branch(root:Path|str, *, career_uid:str, players:list[dict], runtime_session:str|None, trigger:str|None, hints_root:Path|str|None=None, career_date:dict|None=None)->dict:
    """Resolve a persistent save-branch namespace from career UID + live state.

    GetSaveUID is treated as career/slot evidence, not sufficient branch identity.
    Continuous forward states stay on the active branch. A rewind/discontinuity must
    be observed twice before a new/known branch is selected. Empty/obviously partial
    populations never become a branch.
    """
    root=Path(root); uid=str(career_uid); rp=registry_path(root,uid)
    reg=_load(rp,{'schema':SCHEMA,'career_uid':uid,'branches':{},'active_branch_id':None,'max_observed_count':0,'pending_candidate':None})
    reg['schema']=SCHEMA; reg['career_uid']=uid; branches=reg.setdefault('branches',{})
    sig=make_signature(players); count=sig['count']; max_count=int(reg.get('max_observed_count') or 0); incoming_ordinal=_date_ordinal(career_date)

    if count<=0:
        reg['pending_candidate']=None; _atomic(rp,reg)
        return {'status':'HOLD','reason':'EMPTY_PLAYER_POPULATION','career_uid':uid,'player_count':count}
    # Very small snapshots from an already-large career are characteristic of FC27's
    # database being mid-load. Do not use a broad percentage threshold: genuinely old
    # saves can contain far fewer generated players than a later season.
    if max_count>=500 and (count<50 or (count<200 and count < int(max_count*0.10))):
        reg['pending_candidate']=None; _atomic(rp,reg)
        return {'status':'HOLD','reason':'PARTIAL_PLAYER_POPULATION','career_uid':uid,'player_count':count,'known_max':max_count}

    active=reg.get('active_branch_id'); active_rec=branches.get(str(active)) if active else None
    if active_rec:
        prev_sig=active_rec.get('last_signature')
        cmp=compare(prev_sig,sig)
        last_ordinal=active_rec.get('last_career_ordinal')
        trusted_screen_load=str(trigger or '').upper() in {'SCREEN_LOADED_BASELINE','CAREER_SETTLED_BASELINE'}
        # A boundary re-sync is a trusted settled snapshot for rewind detection, but it is
        # not treated as a deliberate load of another save point (see block below).
        trusted_rewind=trusted_screen_load or str(trigger or '').upper()=='BOUNDARY_RESYNC'
        date_rewind=bool(incoming_ordinal is not None and isinstance(last_ordinal,int) and incoming_ordinal < (last_ordinal if trusted_rewind else last_ordinal-1))

        # A trusted screen-load boundary with a different date can be a deliberate
        # load of another save point in the same FC27 slot. Before treating a forward
        # date as ordinary progression, resume a previously known branch anchored at
        # that date when its player identity also matches.
        if trusted_screen_load and incoming_ordinal is not None and isinstance(last_ordinal,int) and incoming_ordinal != last_ordinal:
            load_matches=[]
            for kbid,krec in branches.items():
                if str(kbid)==str(active): continue
                if krec.get('rollback_from_storage_key') and str(krec.get('rollback_policy') or '') != 'DATE_ALIGNED_V1': continue
                kord=krec.get('last_career_ordinal')
                if not isinstance(kord,int) or abs(kord-incoming_ordinal)>1: continue
                kcmp=compare(krec.get('last_signature'),sig)
                if _branch_match(kcmp) or _sparse_continuity(krec.get('last_signature'),sig):
                    load_matches.append((kcmp.get('identity_overlap',0.0),kbid,krec,kcmp))
            if load_matches:
                load_matches.sort(reverse=True,key=lambda x:x[0]); _,bid,rec,kcmp=load_matches[0]
                reg['active_branch_id']=bid; rec['last_signature']=sig; rec['last_seen']=time.time(); rec['last_runtime_session']=str(runtime_session or '')
                rec['last_career_ordinal']=incoming_ordinal; reg['pending_candidate']=None; reg['max_observed_count']=max(max_count,count); _atomic(rp,reg)
                return {'status':'OK','state':'RESUME_KNOWN_LOADED_BRANCH','career_uid':uid,'branch_id':bid,'storage_key':rec['storage_key'],'similarity':kcmp,'player_count':count,'loaded_date_switch':True}

        if (_continuity(cmp) or _sparse_continuity(prev_sig,sig)) and not date_rewind:
            active_rec['last_signature']=sig; active_rec['last_seen']=time.time(); active_rec['last_runtime_session']=str(runtime_session or '')
            if incoming_ordinal is not None: active_rec['last_career_ordinal']=incoming_ordinal
            reg['max_observed_count']=max(max_count,count); reg['pending_candidate']=None; _atomic(rp,reg)
            return {'status':'OK','state':'CONTINUE_ACTIVE_BRANCH','career_uid':uid,'branch_id':active,'storage_key':active_rec['storage_key'],'similarity':cmp,'player_count':count,'date_rewind':False}
        if date_rewind:
            # First try a branch already observed at the loaded date. Re-loading the same
            # FC27 save should resume the same Academy branch rather than manufacture
            # another branch on every visit.
            rewind_matches=[]
            for kbid,krec in branches.items():
                if str(kbid)==str(active): continue
                kcmp=compare(krec.get('last_signature'),sig)
                kord=krec.get('last_career_ordinal')
                if isinstance(kord,int) and incoming_ordinal is not None and abs(kord-incoming_ordinal)<=1 and (_branch_match(kcmp) or _sparse_continuity(krec.get('last_signature'),sig)):
                    rewind_matches.append((kcmp.get('identity_overlap',0.0),kbid,krec,kcmp))
            if rewind_matches:
                rewind_matches.sort(reverse=True,key=lambda x:x[0]); _,bid,rec,kcmp=rewind_matches[0]
                reg['active_branch_id']=bid; rec['last_signature']=sig; rec['last_seen']=time.time(); rec['last_runtime_session']=str(runtime_session or '')
                rec['last_career_ordinal']=incoming_ordinal; reg['pending_candidate']=None; reg['max_observed_count']=max(max_count,count); _atomic(rp,reg)
                return {'status':'OK','state':'RESUME_KNOWN_REWIND_BRANCH','career_uid':uid,'branch_id':bid,'storage_key':rec['storage_key'],'similarity':kcmp,'player_count':count,'rewind_days':int(last_ordinal-incoming_ordinal)}

            pending=reg.get('pending_candidate') or {}
            same_rewind=bool(pending.get('reason')=='CAREER_DATE_REWIND' and pending.get('signature') and (_candidate_same(compare(pending.get('signature'),sig)) or _small_candidate_same(pending.get('signature'),sig)))
            # SCREEN_LOADED_BASELINE is emitted only after FC27 reports that the career
            # screen has finished loading. Its full snapshot is authoritative enough to
            # resolve a backwards date immediately; waiting for another in-game event
            # previously forced the user to advance a day just to finish loading.
            trusted_load=str(trigger or '').upper() in {'SCREEN_LOADED_BASELINE','CAREER_SETTLED_BASELINE','BOUNDARY_RESYNC'}
            if same_rewind or trusted_load:
                bid=_new_branch_id(uid,sig); key=branch_storage_key(uid,bid)
                if bid in branches:
                    suffix=str(incoming_ordinal or 'rw')
                    bid=bid+'_rw'+suffix; key=branch_storage_key(uid,bid)
                    n=2
                    while bid in branches:
                        bid=_new_branch_id(uid,sig)+'_rw'+suffix+'_'+str(n); key=branch_storage_key(uid,bid); n+=1
                rollback_key=active_rec.get('storage_key')
                branches[bid]={'branch_id':bid,'storage_key':key,'created':time.time(),'last_seen':time.time(),'anchor_signature':sig,'last_signature':sig,'created_from_active_branch':active,'rollback_from_storage_key':rollback_key,'rollback_policy':'DATE_ALIGNED_V1','last_career_ordinal':incoming_ordinal}
                reg['active_branch_id']=bid; reg['pending_candidate']=None; reg['max_observed_count']=max(max_count,count); _atomic(rp,reg)
                return {'status':'OK','state':'INITIALISE_REWIND_BRANCH','career_uid':uid,'branch_id':bid,'storage_key':key,'player_count':count,'rewind_days':int(last_ordinal-incoming_ordinal),'rollback_from_storage_key':rollback_key,'rollback_date':career_date or {}}
            reg['pending_candidate']={'signature':sig,'seen':1,'first_seen':time.time(),'runtime_session':str(runtime_session or ''),'trigger':str(trigger or ''),'reason':'CAREER_DATE_REWIND','career_ordinal':incoming_ordinal}
            _atomic(rp,reg)
            return {'status':'HOLD','reason':'CAREER_DATE_REWIND_CONFIRMATION_REQUIRED','career_uid':uid,'player_count':count,'active_branch_id':active,'candidate_seen':1,'rewind_days':int(last_ordinal-incoming_ordinal)}

    # Try a previously known branch before creating another one.
    matches=[]
    for bid,rec in branches.items():
        prev_sig=rec.get('last_signature')
        cmp=compare(prev_sig,sig)
        rec_ord=rec.get('last_career_ordinal'); date_ok=not (incoming_ordinal is not None and isinstance(rec_ord,int) and incoming_ordinal < rec_ord-1)
        if (_branch_match(cmp) or _sparse_continuity(prev_sig,sig)) and date_ok:
            score=(cmp['identity_overlap']*100)-(min(cmp['age_median_delta'],10)*20)-(min(cmp['ovr_mean_delta'],20)*2)+(cmp['count_ratio']*10)
            if cmp['comparable'] < 40: score += 25
            matches.append((score,bid,rec,cmp))
    if matches:
        matches.sort(reverse=True,key=lambda x:x[0]); _,bid,rec,cmp=matches[0]
        reg['active_branch_id']=bid; rec['last_signature']=sig; rec['last_seen']=time.time(); rec['last_runtime_session']=str(runtime_session or '')
        if incoming_ordinal is not None: rec['last_career_ordinal']=incoming_ordinal
        reg['max_observed_count']=max(max_count,count); reg['pending_candidate']=None; _atomic(rp,reg)
        return {'status':'OK','state':'RESUME_KNOWN_BRANCH','career_uid':uid,'branch_id':bid,'storage_key':rec['storage_key'],'similarity':cmp,'player_count':count}

    # A Save As under a new UID can carry a lightweight parent hint written by Lua.
    # Do not trust the hint alone: require the incoming live identities to match the
    # hinted parent's persisted world before cloning any progression state.
    hint_base=Path(hints_root) if hints_root is not None else root
    hint=_load(hint_base/'branch_hints'/f'{_safe(uid)}.json',{})
    hinted_storage=str(hint.get('parent_storage_key') or '')
    hinted_branch=str(hint.get('parent_branch_id') or '')
    if not branches and hinted_storage:
        pw=root/'saves'/_safe(hinted_storage)/'generated_world.json'
        if pw.exists():
            parent=_load(pw,{})
            ps=[]
            for cp in (parent.get('players') or {}).values():
                g=cp.get('game') or {}
                if g: ps.append(g)
            pc=compare(make_signature(ps),sig)
            parent_date=_date_ordinal((parent.get('career') or {}).get('date'))
            forward_date=parent_date is not None and incoming_ordinal is not None and incoming_ordinal>=parent_date
            identities_match=(pc['comparable']>=40 and pc['identity_overlap']>=0.92 and pc['age_median_delta']<=0.5 and pc['ovr_mean_delta']<=4.0) or _sparse_continuity(make_signature(ps),sig)
            if forward_date and identities_match and str(hint.get('runtime_session') or '')==str(runtime_session or ''):
                bid=_new_branch_id(uid,sig); key=branch_storage_key(uid,bid)
                branches[bid]={'branch_id':bid,'storage_key':key,'created':time.time(),'last_seen':time.time(),'anchor_signature':sig,'last_signature':sig,'branched_from_storage_key':hinted_storage,'branched_from_branch_id':hinted_branch or None,'last_career_ordinal':incoming_ordinal}
                reg['active_branch_id']=bid; reg['max_observed_count']=max(max_count,count); reg['pending_candidate']=None; _atomic(rp,reg)
                return {'status':'OK','state':'BRANCH_FROM_SAVE_AS_HINT','career_uid':uid,'branch_id':bid,'storage_key':key,'parent_storage_key':hinted_storage,'parent_branch_id':hinted_branch or None,'similarity':pc,'player_count':count}

    # A full baseline emitted only after the Lua startup-settle quarantine is an
    # authoritative first state for a previously unseen career. Requiring a second
    # in-game event here made users advance one day merely to initialise Academy
    # Engine, which v1.24 explicitly avoids. Existing/ambiguous branches still use
    # the confirmation logic below.
    trusted_initial=str(trigger or '').upper() in {'CAREER_SETTLED_BASELINE','SCREEN_LOADED_BASELINE','SAVE_STABILIZED','BOUNDARY_RESYNC'}
    if not branches and trusted_initial:
        bid=_new_branch_id(uid,sig); key=branch_storage_key(uid,bid)
        branches[bid]={'branch_id':bid,'storage_key':key,'created':time.time(),'last_seen':time.time(),'anchor_signature':sig,'last_signature':sig,'created_from_active_branch':None,'last_career_ordinal':incoming_ordinal}
        reg['active_branch_id']=bid; reg['max_observed_count']=max(max_count,count); reg['pending_candidate']=None; _atomic(rp,reg)
        return {'status':'OK','state':'INITIALISE_TRUSTED_BASELINE','career_uid':uid,'branch_id':bid,'storage_key':key,'parent_branch_id':None,'player_count':count}

    # Other discontinuities are data-stabilised: require two substantially identical snapshots.
    pending=reg.get('pending_candidate') or {}
    same=False; pcmp=None
    if pending.get('signature'):
        pcmp=compare(pending.get('signature'),sig)
        same=_candidate_same(pcmp) or (not branches and _small_candidate_same(pending.get('signature'),sig))
    if not same:
        reg['pending_candidate']={'signature':sig,'seen':1,'first_seen':time.time(),'runtime_session':str(runtime_session or ''),'trigger':str(trigger or '')}
        _atomic(rp,reg)
        return {'status':'HOLD','reason':'BRANCH_DISCONTINUITY_CONFIRMATION_REQUIRED','career_uid':uid,'player_count':count,'active_branch_id':active,'candidate_seen':1}

    seen=int(pending.get('seen') or 1)+1
    if seen<2:
        pending['seen']=seen; pending['signature']=sig; reg['pending_candidate']=pending; _atomic(rp,reg)
        return {'status':'HOLD','reason':'BRANCH_DISCONTINUITY_CONFIRMATION_REQUIRED','career_uid':uid,'player_count':count,'candidate_seen':seen}

    bid=_new_branch_id(uid,sig); key=branch_storage_key(uid,bid)
    # Extremely unlikely hash collision: suffix deterministically if key exists for different anchor.
    if bid in branches and not _branch_match(compare(branches[bid].get('anchor_signature'),sig)):
        bid=bid+'_'+hashlib.sha256(sig['state_digest'].encode()).hexdigest()[:4]; key=branch_storage_key(uid,bid)
    branches[bid]={'branch_id':bid,'storage_key':key,'created':time.time(),'last_seen':time.time(),'anchor_signature':sig,'last_signature':sig,'created_from_active_branch':active,'last_career_ordinal':incoming_ordinal}
    reg['active_branch_id']=bid; reg['max_observed_count']=max(max_count,count); reg['pending_candidate']=None; _atomic(rp,reg)
    return {'status':'OK','state':'INITIALISE_NEW_BRANCH','career_uid':uid,'branch_id':bid,'storage_key':key,'parent_branch_id':None,'similarity_to_candidate':pcmp,'player_count':count}


def activate_exact_save_branch(root:Path|str, *, career_uid:str, players:list[dict], runtime_session:str|None, career_date:dict|None, fingerprint:str, source_storage_key:str|None=None)->dict:
    """Activate a deterministic branch for an exact previously observed FC27 save.

    This preserves any later/unsaved Academy timeline in its own branch while the
    reloaded save resumes a state namespace tied to the exact FC27 fingerprint.
    """
    root=Path(root); uid=str(career_uid); rp=registry_path(root,uid)
    reg=_load(rp,{'schema':SCHEMA,'career_uid':uid,'branches':{},'active_branch_id':None,'max_observed_count':0,'pending_candidate':None})
    reg['schema']=SCHEMA; reg['career_uid']=uid; branches=reg.setdefault('branches',{})
    sig=make_signature(players); incoming_ordinal=_date_ordinal(career_date)
    suffix=str(fingerprint or '')[:12] or sig.get('state_digest','')[:12]
    bid='save_'+suffix
    key=branch_storage_key(uid,bid)
    rec=branches.get(bid)
    if not rec:
        rec={'branch_id':bid,'storage_key':key,'created':time.time(),'anchor_signature':sig,
             'created_from_active_branch':reg.get('active_branch_id'),'exact_save_fingerprint':str(fingerprint or ''),
             'source_storage_key':str(source_storage_key or ''),'last_career_ordinal':incoming_ordinal}
        branches[bid]=rec
    rec['last_signature']=sig; rec['last_seen']=time.time(); rec['last_runtime_session']=str(runtime_session or '')
    rec['exact_save_fingerprint']=str(fingerprint or '')
    if incoming_ordinal is not None: rec['last_career_ordinal']=incoming_ordinal
    reg['active_branch_id']=bid; reg['pending_candidate']=None
    reg['max_observed_count']=max(int(reg.get('max_observed_count') or 0),int(sig.get('count') or 0))
    _atomic(rp,reg)
    return {'status':'OK','state':'RESUME_EXACT_SAVE','career_uid':uid,'branch_id':bid,'storage_key':key,
            'source_storage_key':str(source_storage_key or ''),'player_count':sig.get('count',0),'fingerprint':str(fingerprint or '')}
