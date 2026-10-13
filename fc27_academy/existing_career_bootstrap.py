"""Bootstrap persistent Football DNA from an already-developed FC27 generated player.

Existing-career players are *adopted*, not rerolled. Their current FC27 attributes,
position, potential, roles and PlayStyles are evidence of the career that already
happened. This module infers a stable DNA profile from that evidence and creates only
small optional coherence proposals. It never writes FC27 directly.
"""
from __future__ import annotations
from dataclasses import dataclass
from statistics import mean
from .football_dna_v2 import ARCHETYPES, ROLE_PREFERENCES, GROUP_ATTRS
from .position_attributes import primary_attributes, normalize_position, is_goalkeeper

@dataclass(frozen=True)
class BootstrapResult:
    player_id: int
    position: str
    archetype: str
    aptitudes: dict
    confidence: float
    source: str
    proposals: tuple


def _avg(attrs, names):
    vals=[float(attrs[n]) for n in names if n in attrs and isinstance(attrs[n],(int,float))]
    return mean(vals) if vals else None


def observed_group_scores(attrs, position):
    """Return 0..1-ish relative group strengths from current FC27 attributes."""
    pos=normalize_position(position)
    groups={}
    allowed=set(primary_attributes(pos))
    for group,names in GROUP_ATTRS.items():
        vals=[n for n in names if n in allowed]
        v=_avg(attrs,vals)
        if v is not None: groups[group]=v
    if not groups: return {}
    baseline=mean(groups.values())
    # Relative aptitude, bounded so one odd FC attribute cannot dominate DNA.
    return {g:round(max(.70,min(1.30,1.0+(v-baseline)/45.0)),3) for g,v in groups.items()}


def _archetype_score(name, position, observed):
    spec=ARCHETYPES[name]
    if normalize_position(position) not in spec["positions"]: return None
    keys=set(observed)&set(spec["weights"])
    if not keys: return None
    # Compare relative shape rather than absolute quality.
    return sum(abs(observed[k]-max(.70,min(1.30,float(spec["weights"][k])))) for k in keys)/len(keys)


def infer_archetype(position, attrs):
    observed=observed_group_scores(attrs,position)
    scored=[]
    for name in ARCHETYPES:
        s=_archetype_score(name,position,observed)
        if s is not None: scored.append((s,name))
    if not scored:
        return "SHOT_STOPPER" if is_goalkeeper(position) else "BOX_TO_BOX", observed, .45
    scored.sort()
    best,name=scored[0]
    second=scored[1][0] if len(scored)>1 else best+.20
    margin=max(0.0,second-best)
    confidence=round(max(.50,min(.95,.68+margin*.9-best*.35)),3)
    return name,observed,confidence


def _coherence_proposals(attrs, dna, position, cap=2):
    """Tiny redistribution proposals for existing saves; quality is not rerolled."""
    allowed=set(primary_attributes(position)); proposals=[]
    apt=dna["aptitudes"]
    for group,names in GROUP_ATTRS.items():
        w=apt.get(group,1.0)
        if abs(w-1.0)<.07: continue
        direction=1 if w>1 else -1
        for field in names:
            if field not in allowed or field not in attrs: continue
            old=int(attrs[field])
            # Existing careers get at most +/-2 and only for clearly characteristic groups.
            delta=min(cap,max(1,round(abs(w-1.0)*8))) * direction
            new=max(1,min(99,old+delta))
            if new!=old:
                proposals.append({"change_type":"EXISTING_CAREER_COHERENCE","field":field,"old":old,"new":new,
                                  "reason":f"Existing-save DNA coherence: {dna['archetype']}","confidence":.78})
    return proposals


def bootstrap_existing_player(snapshot, career_seed, *, propose_initial_coherence=True):
    pid=int(snapshot.get("player_id",snapshot.get("playerid")))
    pos=normalize_position(snapshot.get("position",snapshot.get("preferredposition1")))
    attrs=dict(snapshot.get("attributes") or {})
    required=primary_attributes(pos)
    missing=[x for x in required if x not in attrs]
    if missing: raise ValueError(f"Incomplete {pos} primary attributes: {','.join(missing)}")
    archetype,observed,confidence=infer_archetype(pos,attrs)
    # Blend observed shape with archetype prior. Current player is the stronger evidence.
    prior=ARCHETYPES[archetype]["weights"]
    keys=set(observed)|set(prior)
    apt={k:round(max(.65,min(1.35,.72*observed.get(k,1.0)+.28*float(prior.get(k,1.0)))),3) for k in keys}
    dna={"archetype":archetype,"aptitudes":apt,"preferred_playstyles":list(ARCHETYPES[archetype]["styles"]),
         "preferred_roles":list(ROLE_PREFERENCES.get(archetype,[])),"position":pos,
         "bootstrap":"EXISTING_FC27_CAREER","observed_at_adoption":observed}
    proposals=_coherence_proposals(attrs,dna,pos) if propose_initial_coherence else []
    return BootstrapResult(pid,pos,archetype,apt,confidence,"FC27_EXISTING_PLAYER_EVIDENCE",tuple(proposals)),dna
