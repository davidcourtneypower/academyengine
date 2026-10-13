"""Newgen starting-PlayStyle planner.

Newly generated players keep their native FC27 PlayStyles, but the Academy Engine
may queue additional normal PlayStyles so 2/3/4/5-style prospects are meaningfully
more common. Targets are deterministic, quality-scaled, position/DNA appropriate,
and never add a starting PlayStyle+.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from .playstyle_development_planner import current_styles
from .position_attributes import FC27_POSITION_IDS
from .playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK, FC27_VERIFIED_BITS, mapping_evidence
from .playstyle_lifetime import normal_cap, ensure_policy, ABSOLUTE_NORMAL_CAP
from .aptitude import aptitude_score

RULES=json.loads((Path(__file__).parent/'data'/'playstyle_generation_rules.json').read_text(encoding='utf-8'))

# Starting distribution targets are *minimum* counts, not
# destructive replacements: FC27-native PlayStyles are always preserved. Stronger
# prospects are substantially more likely to target 3/4/5 normal PlayStyles.
# The values are intentionally explicit and deterministic for the production enrichment policy.
TARGET_COUNT_PROFILES={
    'DEVELOPING': ((0,.22),(1,.40),(2,.25),(3,.09),(4,.03),(5,.01)),
    'PROMISING':  ((0,.10),(1,.28),(2,.34),(3,.18),(4,.07),(5,.03)),
    'HIGH':       ((0,.04),(1,.18),(2,.34),(3,.25),(4,.13),(5,.06)),
    'ELITE':      ((0,.01),(1,.09),(2,.27),(3,.30),(4,.20),(5,.13)),
}
MAX_STARTING_NORMAL_PLAYSTYLES=5


def _positions(game):
    out=[]
    for i in range(1,8):
        v=game.get(f'preferredposition{i}')
        try: v=int(v)
        except (TypeError,ValueError): continue
        p=FC27_POSITION_IDS.get(v)
        if p and p not in out: out.append(p)
    return out


def _u01(pid, checkpoint_id):
    b=f'FC27AE_V124_NEWGEN|{pid}|{checkpoint_id}'.encode()
    return int.from_bytes(hashlib.sha256(b).digest()[:8],'big')/2**64


def _quality_band(quality):
    if quality < 60: return 'DEVELOPING'
    if quality < 70: return 'PROMISING'
    if quality < 80: return 'HIGH'
    return 'ELITE'


def _target_count(pid, checkpoint_id, quality):
    band=_quality_band(quality); roll=_u01(pid,str(checkpoint_id)+'|COUNT')
    acc=0.0
    for count,prob in TARGET_COUNT_PROFILES[band]:
        acc += prob
        if roll < acc:
            return int(count),band,roll
    return MAX_STARTING_NORMAL_PLAYSTYLES,band,roll


def _candidate_styles(player, game, positions):
    attrs=game.get('attributes') or {}
    dna=(player.get('engine') or {}).get('football_dna') or player.get('dna') or {}
    apt=dna.get('aptitudes') or dna.get('aptitude') or {}
    rows=[]
    # v1.24.10: only offer styles that exist in FC27's bitfield for this player's
    # field. Rules for Quick Reflexes/Trivela/Aerial/Power Header/Flair have no FC27
    # bit; picking one wasted a starting slot and left the player below target.
    try: is_gk=int(game.get('preferredposition1'))==0
    except (TypeError,ValueError): is_gk=False
    mapping=PLAYSTYLE2_GK if is_gk else PLAYSTYLE1
    for name,rule in RULES.items():
        if name not in mapping: continue
        matched=[p for p in positions if p in rule.get('positions',[])]
        if not matched: continue
        vals=[float(attrs.get(a,45) or 45) for a in rule.get('attributes',[])]; fit=sum(vals)/len(vals) if vals else 45.0
        dna_fit=aptitude_score(apt.get(rule.get('aptitude')))
        affinity=0.0
        if name=='Long Throw': affinity -= 18.0 if 'CB' in matched else 10.0
        if name=='Rapid' and any(x in matched for x in ('LB','RB')): affinity -= 8.0
        if name in ('Anticipate','Intercept','Jockey','Block','Aerial','Aerial Fortress','Bruiser','Enforcer') and any(x in matched for x in ('CB','CDM','LB','RB')): affinity += 4.0
        if name in ('Incisive Pass','Tiki Taka','Technical','First Touch','Pinged Pass','Long Ball Pass') and any(x in matched for x in ('CM','CAM','CDM')): affinity += 3.0
        score=fit + (dna_fit-50.0)*0.12 + affinity
        rows.append((score,fit,name,matched))
    rows.sort(key=lambda x:(-x[0],-x[1],x[2]))
    return rows


def _pick_additions(pid, checkpoint_id, candidates, owned, needed):
    """Choose distinct plausible styles, with controlled variation among top fits."""
    available=[r for r in candidates if r[2] not in owned]
    out=[]
    for slot in range(max(0,int(needed))):
        if not available: break
        top=available[:min(4,len(available))]
        roll=_u01(pid,f'{checkpoint_id}|STYLE|{slot}')
        # Strong bias to best fit, but enough variation that cohorts are not clones.
        if roll < .52: idx=0
        elif roll < .78: idx=min(1,len(top)-1)
        elif roll < .93: idx=min(2,len(top)-1)
        else: idx=min(3,len(top)-1)
        chosen=top[idx]; out.append(chosen); available.remove(chosen)
    return out


def audit_world(world, checkpoint_id=None):
    cohort=[]; proposals=[]; target_hist={str(i):0 for i in range(MAX_STARTING_NORMAL_PLAYSTYLES+1)}
    projected_hist={str(i):0 for i in range(MAX_STARTING_NORMAL_PLAYSTYLES+1)}; additions_by_player={}
    for p in (world.get('players') or {}).values():
        if not p.get('observed_this_checkpoint',False): continue
        is_new=bool(p.get('generation_new_this_checkpoint',False))
        if not is_new: continue
        g=p.get('game') or {}; normal,plus,is_gk=current_styles(g); positions=_positions(g)
        pid=int(p.get('playerid',0)); quality=.60*float(g.get('overallrating') or 0)+.40*float(g.get('potential') or 0)
        ensure_policy(p); lifetime_cap=min(ABSOLUTE_NORMAL_CAP,normal_cap(p))
        target,band,count_roll=_target_count(pid,checkpoint_id,quality)
        native_count=len(normal); target=max(native_count,target)  # never reduce FC27-native richness
        target=min(MAX_STARTING_NORMAL_PLAYSTYLES,lifetime_cap,target)
        row={'playerid':pid,'age':g.get('age'),'ovr':g.get('overallrating'),'potential':g.get('potential'),'positions':positions,
             'normal_count':native_count,'plus_count':len(plus),'quality':round(quality,1),'quality_band':band,'target_count':target,'lifetime_cap':lifetime_cap,'count_roll':round(count_roll,3)}
        cohort.append(row); target_hist[str(target)]+=1
        needed=max(0,target-native_count)
        candidates=_candidate_styles(p,g,positions)
        picks=_pick_additions(pid,checkpoint_id,candidates,set(normal),needed)
        additions_by_player[str(pid)]=len(picks)
        for slot,(score,fit,style,matched) in enumerate(picks):
            mapping=PLAYSTYLE2_GK if is_gk else PLAYSTYLE1; field='trait2' if is_gk else 'trait1'; bit=mapping.get(style)
            verified=bool(bit is not None and (field,int(bit)) in FC27_VERIFIED_BITS)
            expected=int(g.get(field,0) or 0)
            # Queue entries are independently rebased to live state before writing.
            proposed=expected|int(bit or 0) if bit is not None else expected
            proposals.append({'playerid':pid,'age':row['age'],'ovr':row['ovr'],'potential':row['potential'],'positions':positions,'matched_positions':matched,
                              'style':style,'fit':round(fit,1),'selection_score':round(score,1),'quality':row['quality'],'quality_band':band,
                              'native_count':native_count,'target_count':target,'addition_slot':slot+1,'field':field,'bit':bit,'expected':expected,'proposed':proposed,
                              'mapping_evidence':mapping_evidence(field,bit) if bit is not None else None,'birthdate':g.get('birthdate'),'nationality':g.get('nationality'),
                              'validation':'READY_NEWGEN_VERIFIED' if verified else 'HOLD_UNVERIFIED_WRITE_MAPPING','operation':'ADD_STARTING_PLAYSTYLE','write_performed':'NO'})
        projected=min(MAX_STARTING_NORMAL_PLAYSTYLES,native_count+len(picks)); projected_hist[str(projected)]+=1
    n=len(cohort)
    native_hist={str(i):0 for i in range(MAX_STARTING_NORMAL_PLAYSTYLES+1)}
    native_5plus=0
    for r in cohort:
        c=int(r['normal_count'])
        if c>=5: native_5plus+=1; native_hist['5']+=1
        else: native_hist[str(c)]+=1
    pct=lambda x: round(100*x/n,1) if n else 0.0
    native_with=sum(1 for r in cohort if r['normal_count']>0)
    projected_with=sum(v for k,v in projected_hist.items() if int(k)>0)
    return {'mode':'RICH_NEWGEN_PLAYSTYLE_PRODUCTION_QUEUE','checkpoint_new':n,'cohort_playerids':[int(r['playerid']) for r in cohort],'native_with_ps':native_with,'native_with_ps_pct':pct(native_with),
            'enrichment_proposals':len(proposals),'players_enriched':sum(1 for v in additions_by_player.values() if v>0),
            'projected_with_ps':projected_with,'projected_with_ps_pct':pct(projected_with),'projected_psplus_added':0,
            'native_count_hist':native_hist,'target_count_hist':target_hist,'projected_count_hist':projected_hist,
            'max_starting_normal_playstyles':MAX_STARTING_NORMAL_PLAYSTYLES,'proposals':proposals,'writes_locked':True,'write_performed':False}
