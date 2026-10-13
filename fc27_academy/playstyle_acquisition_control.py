"""Controlled normal-PlayStyle production acquisition gate."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
from .playstyle_development_planner import current_styles
from .runtime_config import normal_threshold, normal_cooldown_days
from .position_attributes import FC27_POSITION_IDS
from .playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK, FC27_VERIFIED_BITS, mapping_evidence
from .playstyle_lifetime import normal_cap, ABSOLUTE_NORMAL_CAP, ensure_policy
from .aptitude import aptitude_score

RULES=json.loads((Path(__file__).parent/'data'/'playstyle_generation_rules.json').read_text(encoding='utf-8'))
COOLDOWN_DAYS=120  # default export; runtime value comes from settings
ATYPICAL_ATTRIBUTE_MIN=78.0
ATYPICAL_SOFT_MIN=70.0
ATYPICAL_SCORE_PENALTY=18.0

def _positions(game):
    out=[]
    for i in range(1,8):
        try:v=int(game.get(f'preferredposition{i}'))
        except (TypeError,ValueError):continue
        p=FC27_POSITION_IDS.get(v)
        if p and p not in out:out.append(p)
    return out

def _fit(player,style):
    game=player.get('game') or {}; rule=RULES.get(style) or {}; pos=_positions(game)
    matched=[p for p in pos if p in (rule.get('positions') or [])]
    attrs=game.get('attributes') or {}; vals=[]
    for a in rule.get('attributes') or []:
        v=attrs.get(a,game.get(a,45))
        try:vals.append(float(v or 45))
        except (TypeError,ValueError):vals.append(45.0)
    attr_fit=sum(vals)/len(vals) if vals else 45.0
    dna=(player.get('engine') or {}).get('football_dna') or player.get('dna') or {}; apt=dna.get('aptitudes') or dna.get('aptitude') or {}
    # v1.24.10: DNA multipliers converted to the 0..100 score this formula expects.
    dna_fit=aptitude_score(apt.get(rule.get('aptitude')))
    affinity=0.0
    if style=='Long Throw':affinity-=18.0 if 'CB' in matched else 10.0
    if style=='Rapid' and any(x in matched for x in ('LB','RB')):affinity-=8.0
    if style in ('Anticipate','Intercept','Jockey','Block','Aerial','Bruiser') and any(x in matched for x in ('CB','CDM','LB','RB')):affinity+=4.0
    if style in ('Incisive Pass','Tiki Taka','Technical','First Touch') and any(x in matched for x in ('CM','CAM','CDM')):affinity+=3.0
    # Natural positional fits receive the full score. Atypical fits are possible
    # only with exceptional supporting attributes and carry a meaningful penalty.
    # This keeps unusual profiles (e.g. a genuinely rapid CB) possible without
    # making them as common as natural positional PlayStyles.
    atypical = not bool(matched)
    plausibility = 'NATURAL_POSITION' if matched else ('ATTRIBUTE_EXCEPTION' if attr_fit >= ATYPICAL_ATTRIBUTE_MIN else 'INSUFFICIENT_ATYPICAL_EVIDENCE')
    penalty = ATYPICAL_SCORE_PENALTY if plausibility == 'ATTRIBUTE_EXCEPTION' else 0.0
    score = 25.0+attr_fit*.45+dna_fit*.20+affinity-penalty
    return round(attr_fit,2),round(dna_fit,2),matched,round(score,3),plausibility


def _near_fit_roll(world, playerid, style, attr_fit):
    if attr_fit < ATYPICAL_SOFT_MIN:return False,0.0
    frac=max(0.0,min(1.0,(float(attr_fit)-ATYPICAL_SOFT_MIN)/(ATYPICAL_ATTRIBUTE_MIN-ATYPICAL_SOFT_MIN)))
    chance=.05+.30*frac
    checkpoint=str(world.get("last_checkpoint_id") or world.get("runtime_day_epoch") or "")
    seed=f"{world.get('storage_key','')}|{playerid}|{style}|{checkpoint}|near_fit".encode("utf-8")
    roll=int.from_bytes(hashlib.sha256(seed).digest()[:8],"big")/float(2**64-1)
    return roll<chance,chance

def _target(game,style):
    is_gk=int(game.get('preferredposition1',-1))==0; mapping=PLAYSTYLE2_GK if is_gk else PLAYSTYLE1
    bit=mapping.get(style); field='trait2' if is_gk else 'trait1'
    if bit is None:return None
    cur=int(game.get(field,0) or 0); return field,cur,cur|int(bit),int(bit)

def audit_world(world):
    threshold=normal_threshold(); cooldown_days=normal_cooldown_days()
    winners=[]; suppressed=[]; held_position=[]; held_cooldown=[]; held_lifetime=[]; ready_players=set(); ready_paths=0
    for p in (world.get('players') or {}).values():
        if not p.get('observed_this_checkpoint',False) or p.get('lifecycle')!='CLUB':continue
        g=p.get('game') or {}; e=p.get('engine') or {}; ensure_policy(p); normal,_,_=current_styles(g); rows=[]
        personal_cap=min(ABSOLUTE_NORMAL_CAP,normal_cap(p)); at_lifetime_cap=len(normal)>=personal_cap or len(normal)>=ABSOLUTE_NORMAL_CAP
        cooldown_remaining=int(e.get('playstyle_acquisition_cooldown_days_remaining',0) or 0)
        for style,val in (e.get('playstyle_progress') or {}).items():
            try:prog=float(val)
            except (TypeError,ValueError):continue
            if prog<threshold or style in normal:continue
            ready_paths+=1; ready_players.add(int(p.get('playerid',0)))
            if at_lifetime_cap:
                held_lifetime.append({'playerid':int(p.get('playerid',0)),'style':str(style),'progress':round(prog,3),'validation':'HOLD_LIFETIME_PLAYSTYLE_CAP','normal_count':len(normal),'personal_cap':personal_cap,'absolute_cap':ABSOLUTE_NORMAL_CAP,'write_performed':'NO'})
                continue
            if cooldown_remaining>0:
                held_cooldown.append({'playerid':int(p.get('playerid',0)),'style':str(style),'progress':round(prog,3),'validation':'HOLD_ACQUISITION_COOLDOWN','cooldown_days_remaining':cooldown_remaining,'write_performed':'NO'})
                continue
            attr_fit,dna_fit,matched,fit_score,plausibility=_fit(p,style)
            base={'playerid':int(p.get('playerid',0)),'style':str(style),'progress':round(prog,3),'attribute_fit':attr_fit,'dna_fit':dna_fit,'matched_positions':matched,'plausibility':plausibility,'write_performed':'NO'}
            if plausibility == 'INSUFFICIENT_ATYPICAL_EVIDENCE':
                won_soft,soft_chance=_near_fit_roll(world,int(p.get('playerid',0)),style,attr_fit)
                base['near_fit_chance']=round(soft_chance*100,1)
                if not won_soft:
                    base['validation']='HOLD_PLAUSIBILITY'; held_position.append(base); continue
                base['plausibility']='NEAR_FIT_OPPORTUNITY'; base['near_fit_roll_won']=True
            target=_target(g,style); verified=bool(target and (target[0],target[3]) in FC27_VERIFIED_BITS)
            base.update(score=round(prog+fit_score,3),target=target,verified=verified); rows.append(base)
        if not rows:continue
        rows.sort(key=lambda r:(-r['score'],-r['attribute_fit'],-r['dna_fit'],r['style']))
        win=rows[0]; t=win.pop('target'); verified=win.pop('verified'); win['rank']=1; win['operation']='ADD_BIT'; win['cooldown_days_after_apply']=cooldown_days
        if t:
            win.update(field=t[0],expected=t[1],proposed=t[2],bit=t[3])
            win['already_owned_bit']=bool(int(t[1]) & int(t[3]))
            win['mapping_name']=FC27_VERIFIED_BITS.get((t[0],t[3]))
            win['mapping_evidence']=mapping_evidence(t[0],t[3]) if verified else 'SCHEMA_ONLY_NOT_PRODUCTION_VERIFIED'
            win['simulated_post_value']=t[2]
            win['simulated_progress_after_receipt']=0.0
            win['simulated_cooldown_days']=cooldown_days
            win['cooldown_starts_on']='SUCCESSFUL_WRITE_RECEIPT_ONLY'
        else:
            win.update(already_owned_bit=False,mapping_name=None,mapping_evidence='NO_TARGET_MAPPING',simulated_post_value=None,simulated_progress_after_receipt=None,simulated_cooldown_days=0,cooldown_starts_on='NEVER_WITHOUT_SUCCESSFUL_RECEIPT')
            win.update(field=None,expected=None,proposed=None,bit=None)
        win['validation']='READY_CONTROLLED_VERIFIED' if verified else 'HOLD_MAPPING'; winners.append(win)
        for rank,row in enumerate(rows[1:],2):
            row.pop('target',None); row.pop('verified',None); row['rank']=rank; row['validation']='HOLD_COMPETING_READY_PATH'; suppressed.append(row)
    verified=sum(x['validation']=='READY_CONTROLLED_VERIFIED' for x in winners); mapping_hold=sum(x['validation']=='HOLD_MAPPING' for x in winners)
    # Cooldown remains a transaction contract only until a successful production receipt exists.
    return {'mode':'PRODUCTION_TRANSACTION_GATE_LOCKED','ready_paths':ready_paths,'ready_players':len(ready_players),'winner_count':len(winners),'suppressed_competing_paths':len(suppressed),'position_holds':len(held_position),'plausibility_holds':len(held_position),'atypical_winners':sum(x.get('plausibility')=='ATTRIBUTE_EXCEPTION' for x in winners),'mapping_holds':mapping_hold,'cooldown_holds':len(held_cooldown),'lifetime_cap_holds':len(held_lifetime),'production_eligible':verified,'cooldown_days':cooldown_days,'winners':winners,'held_position':held_position,'held_cooldown':held_cooldown,'held_lifetime':held_lifetime,'suppressed':suppressed,'verified_candidates':[x for x in winners if x['validation']=='READY_CONTROLLED_VERIFIED'],'verified_candidate_count':verified,'cooldown_simulation_only':True,'raw_ready_diagnostic_only':True,'writes_locked':True,'write_performed':False}
