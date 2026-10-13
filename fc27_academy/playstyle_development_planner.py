from __future__ import annotations
from .path_history_store import editable_history
import json, hashlib, random
from .aptitude import aptitude_score
from pathlib import Path
from .playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK
from .playstyle_lifetime import normal_cap, plus_addition_slots, ensure_policy, ABSOLUTE_NORMAL_CAP
from .runtime_config import normal_threshold, plus_threshold, normal_progress_multiplier, plus_progress_multiplier
RULES=json.loads((Path(__file__).parent/'data'/'playstyle_generation_rules.json').read_text(encoding='utf-8'))
SUPPORTED=set(PLAYSTYLE1)|set(PLAYSTYLE2_GK); NORMAL_THRESHOLD=100.0; PLUS_THRESHOLD=180.0
# Calibrated base rates; GUI multipliers are applied live on top.
# v1.24.10: DNA is now read on its real scale. In v1.24.09 every player received a
# flat DNA factor of ~0.707; with correct scaling a neutral player gets ~1.033. The
# base rates are rescaled by 0.707/1.033 so the population-average pace from native
# growth is unchanged and DNA only redistributes it between strong/weak aptitudes.
NORMAL_PROGRESS_RATE=0.924
PLUS_PROGRESS_RATE=0.958
UNMAPPED=set(RULES)-SUPPORTED
def _decode(value,mapping):
    try:value=int(value or 0)
    except (TypeError,ValueError):value=0
    return {n for n,b in mapping.items() if value & b}
def current_styles(game):
    is_gk=int(game.get('preferredposition1',-1))==0; normal=_decode(game.get('trait1'),PLAYSTYLE1); plus=_decode(game.get('icontrait1'),PLAYSTYLE1)
    if is_gk: normal|=_decode(game.get('trait2'),PLAYSTYLE2_GK); plus|=_decode(game.get('icontrait2'),PLAYSTYLE2_GK)
    return normal,plus,is_gk
def _aptitudes(player):
    dna=(player.get('engine') or {}).get('football_dna') or player.get('dna') or {}; return dna.get('aptitudes') or dna.get('aptitude') or {}

def _player_rng(playerid, checkpoint_id):
    # One deterministic generator per player per checkpoint (was one SHA-256 per
    # style per checkpoint). Same inputs always replay the same rolls.
    seed=hashlib.sha256(f"FC27AE_TRAINING_V12410|{playerid}|{checkpoint_id}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(seed[:8],"big"))

def _checkpoint_roll(playerid, style, checkpoint_id, lane="normal"):
    seed=f"{playerid}|{style}|{checkpoint_id}|{lane}".encode("utf-8")
    n=int.from_bytes(hashlib.sha256(seed).digest()[:8],"big")
    return n/float(2**64-1)

# Static per-style data, computed once (v1.24.10 performance).
def _style_table(names):
    out=[]
    for style in sorted(names):
        rule=RULES.get(style)
        if not rule: continue
        attrs=tuple(rule.get('attributes') or ())
        out.append((style,rule,attrs,frozenset(attrs),rule.get('aptitude')))
    return tuple(out)
_OUTFIELD_STYLES=_style_table(PLAYSTYLE1)
_GK_STYLES=_style_table(PLAYSTYLE2_GK)

def _attr_fit(game,attrs_tuple):
    attrs=game.get("attributes") or {}
    if not attrs_tuple: return 45.0
    total=0.0
    for a in attrs_tuple:
        v=attrs.get(a,game.get(a,45))
        try: total+=float(v or 45)
        except (TypeError,ValueError): total+=45.0
    return total/len(attrs_tuple)

def _training_from_fit(attr_fit, dna, lane, days, rng=None, roll=None):
    chance=max(.04,min(.18,.04+max(0,attr_fit-50)*.0025+max(0,dna-50)*.0015))
    if rng is not None:
        r=rng.random; hits=0
        for _ in range(days):
            if r()<chance: hits+=1
    else:
        hits=sum(1 for d in range(days) if roll(d)<chance)
    if not hits: return 0.0,chance
    amount=max(.08,min(.55,.08+(attr_fit-45)*.006+(dna-50)*.004))
    if lane=="plus": amount*=.45
    return round(amount*hits,4),chance

def _passive_training_gain(player, style, rule, apt, checkpoint_id, lane="normal", days=1, rng=None):
    # Small deterministic development opportunity when FC27 attributes do not rise.
    # This represents training/repetition, not a fake native attribute increase.
    # v1.24.10: one opportunity per elapsed career day (was one per snapshot, so
    # merged/coalesced days lost their training chances), and DNA on its real scale.
    game=player.get("game") or {}
    attr_fit=_attr_fit(game,tuple(rule.get("attributes") or ()))
    dna=aptitude_score(apt.get(rule.get("aptitude")))
    days=max(1,int(days or 1)); pid=int(player.get("playerid",0) or 0)
    return _training_from_fit(attr_fit,dna,lane,days,rng=rng,roll=lambda d:_checkpoint_roll(pid,str(style),f"{checkpoint_id}|{d}",lane))

_DROPPED_META_KEYS=('last_base_rate','last_dna_multiplier','last_training_chance','last_career_date')

def _record(meta_map,style,old,new,applied,checkpoint_id,dev_count,career_date,growth,attrset,mult,base_rate,dna_mult,relevant,passive_chance):
    meta=meta_map.setdefault(style,{})
    src={k:v for k,v in growth.items() if k in attrset}
    # v1.24.10: meta keeps only fields the UI reads; per-step detail lives in the
    # (externalised) path history. Constant/duplicated keys made up ~18 MB of a
    # 7,240-player world file that is rewritten every checkpoint.
    for k in _DROPPED_META_KEYS: meta.pop(k,None)
    meta.update({'last_increment':round(applied,3),'last_checkpoint_id':checkpoint_id,'last_checkpoint_count':dev_count,'last_source_attributes':src,'last_multiplier':round(float(mult),3),'last_progress_source':'NATIVE_ATTRIBUTE_GROWTH' if relevant>0 else 'TRAINING_OPPORTUNITY'})
    hist=editable_history(meta); hist.append({'checkpoint_id':checkpoint_id,'career_date':dict(career_date or {}),'from':round(old,3),'to':round(new,3),'increment':round(applied,3),'source_attributes':dict(src),'multiplier':meta['last_multiplier'],'source':meta.get('last_progress_source')})
    if len(hist)>12: del hist[:-12]

def update_from_evidence(player,evidence,checkpoint_id=None,career_date=None,training_days=1):
    engine=player.setdefault('engine',{}); ns=engine.setdefault('playstyle_progress',{}); ps=engine.setdefault('playstyle_plus_progress',{})
    dev_count=int(engine.get('playstyle_development_checkpoint_count',0) or 0)+1
    engine['playstyle_development_checkpoint_count']=dev_count
    normal_meta=engine.setdefault('playstyle_progress_meta',{})
    plus_meta=engine.setdefault('playstyle_plus_progress_meta',{})
    nmult=normal_progress_multiplier(); pmult=plus_progress_multiplier()
    nthreshold=normal_threshold(); pthreshold=plus_threshold(); nrate=NORMAL_PROGRESS_RATE*nmult; prate=PLUS_PROGRESS_RATE*pmult
    game=player.get('game') or {}; normal,plus,is_gk=current_styles(game)
    growth={k:int(v) for k,v in (evidence.get('attribute_changes') or {}).items() if isinstance(v,(int,float)) and v>0}
    apt=_aptitudes(player)
    ensure_policy(player)
    personal_cap=normal_cap(player); normal_slots=max(0,min(ABSOLUTE_NORMAL_CAP,personal_cap)-len(normal)); plus_slots=plus_addition_slots(player)
    events=0; ready=[]; plus_ready=[]
    ncool=int(engine.get('playstyle_acquisition_cooldown_days_remaining',0) or 0)>0
    pcool=int(engine.get('playstyle_plus_cooldown_days_remaining',0) or 0)>0
    days=max(1,int(training_days or 1))
    rng=None; scores={}
    lost_any=bool(((engine.get('decline') or {}).get('lost')))
    if lost_any:
        from .playstyle_decline import reacquire_blocked as _reacquire_blocked
    for style,rule,attrs_t,attrset,aptg in (_GK_STYLES if is_gk else _OUTFIELD_STYLES):
        owned=style in normal
        # Completed/owned paths retain history without repeated zero-gain work.
        if style in plus: continue
        if owned:
            if plus_slots<=0 or pcool or float(ps.get(style,0) or 0)>=pthreshold: continue
        else:
            if normal_slots<=0 or ncool or float(ns.get(style,0) or 0)>=nthreshold: continue
            # v1.24.36: a PlayStyle lost to age is not re-earned unless its attributes recover.
            if lost_any and _reacquire_blocked(player,style): continue
        dna=scores.get(aptg)
        if dna is None: dna=scores[aptg]=aptitude_score(apt.get(aptg))
        dna_mult=max(.65,min(1.35,.70+dna/150.0))
        relevant=0
        if growth:
            for a in attrs_t: relevant+=growth.get(a,0)
        passive_chance=0.0
        if relevant>0:
            gain=round(relevant*2.5*dna_mult,3)
        else:
            if rng is None: rng=_player_rng(int(player.get('playerid',0) or 0),checkpoint_id)
            gain,passive_chance=_training_from_fit(_attr_fit(game,attrs_t),dna,'plus' if owned else 'normal',days,rng=rng)
            if gain<=0: continue
        if not owned:
            old=float(ns.get(style,0)); new=min(nthreshold,old+gain*nrate); ns[style]=round(new,3); events+=1
            _record(normal_meta,style,old,new,max(0.0,new-old),checkpoint_id,dev_count,career_date,growth,attrset,nmult,NORMAL_PROGRESS_RATE,dna_mult,relevant,passive_chance)
            if old<nthreshold<=new: ready.append(style)
        else:
            old=float(ps.get(style,0)); new=min(pthreshold,old+gain*.55*prate); ps[style]=round(new,3); events+=1
            _record(plus_meta,style,old,new,max(0.0,new-old),checkpoint_id,dev_count,career_date,growth,attrset,pmult,PLUS_PROGRESS_RATE,dna_mult,relevant,passive_chance)
            if old<pthreshold<=new: plus_ready.append(style)
    return {'progress_events':events,'normal_ready':ready,'plus_ready':plus_ready,'normal_styles':len(normal),'plus_styles':len(plus),'is_gk':is_gk}
def audit_world(world):
    tracked=progressing=ready=plus_ready=0; mx=mxp=0.0; nthreshold=normal_threshold(); pthreshold=plus_threshold()
    for p in world.get('players',{}).values():
        tracked+=1; eng=p.get('engine') or {}; ns=eng.get('playstyle_progress') or {}; ps=eng.get('playstyle_plus_progress') or {}
        if ns or ps:progressing+=1
        if ns:mx=max(mx,max(map(float,ns.values())))
        if ps:mxp=max(mxp,max(map(float,ps.values())))
        normal,plus,_=current_styles(p.get('game') or {}); ready+=sum(float(v)>=nthreshold and s not in normal for s,v in ns.items()); plus_ready+=sum(float(v)>=pthreshold and s in normal and s not in plus for s,v in ps.items())
    return {'ps_tracked':tracked,'ps_progressing':progressing,'ps_ready':ready,'ps_plus_ready':plus_ready,'max_ps_progress':round(mx,3),'max_ps_plus_progress':round(mxp,3),'normal_threshold':nthreshold,'plus_threshold':pthreshold,'unmapped_catalogue_entries':len(UNMAPPED)}
