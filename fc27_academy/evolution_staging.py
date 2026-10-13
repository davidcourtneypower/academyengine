"""Conservative evolution -> verified-write staging.

This module stages Role tier upgrades only; it never writes FC27 directly.
A role can move from Role+ (1..52) to the matching Role++ (101..152) only when
observed FC27 development has accumulated enough evidence for that same semantic role.
Free agents are excluded because they have no current club-development context.
"""
from __future__ import annotations
from dataclasses import dataclass
from .staged_sync import Change, make_changeset
from .role_sync import decode_role

ROLE_PLUS_TO_PLUSPLUS_THRESHOLD = 100.0


def _semantic(role_id:int)->str|None:
    label=decode_role(int(role_id))
    if label.startswith("UNKNOWN") or label=="None": return None
    core=label.split(" ",1)[1] if " " in label else label
    return core.rstrip("+")

@dataclass(frozen=True)
class StagePlan:
    changeset: object|None
    eligible_players:int
    staged_changes:int
    held_free_agents:int
    reasons:dict


def plan_verified_role_changes(world:dict, *, save_uid:str, checkpoint_id:str,
                               threshold:float=ROLE_PLUS_TO_PLUSPLUS_THRESHOLD,
                               max_changes:int=3)->StagePlan:
    candidates=[]; eligible=held_free=0; reasons={}
    for key,p in sorted((world.get("players") or {}).items(), key=lambda kv:int(kv[0])):
        if not p.get("observed_this_checkpoint",False):
            reasons["NOT_OBSERVED"] = reasons.get("NOT_OBSERVED",0)+1; continue
        if p.get("lifecycle") != "CLUB":
            held_free += p.get("lifecycle")=="FREE_AGENT"
            reasons["NOT_ACTIVE_CLUB"] = reasons.get("NOT_ACTIVE_CLUB",0)+1; continue
        eligible += 1
        game=p.get("game") or {}; roles=list(game.get("roles") or [])
        ledger=((p.get("engine") or {}).get("role_progress") or {})
        for idx,rv in enumerate(roles[:5],1):
            try: rid=int(rv)
            except Exception: continue
            if not (1 <= rid <= 52): continue  # never downgrade/rewrite ++ or unknown
            semantic=_semantic(rid)
            evidence=float(ledger.get(semantic,0.0)) if semantic else 0.0
            if evidence < threshold: continue
            candidates.append((evidence,int(key),idx,rid,semantic))
    # Highest evidence first; deterministic tie breaks.
    candidates.sort(key=lambda x:(-x[0],x[1],x[2]))
    changes=[]
    for evidence,pid,idx,rid,semantic in candidates[:max(0,int(max_changes))]:
        changes.append(Change(pid,f"role{idx}",rid,rid+100,"ROLE",
                              f"OBSERVED_ROLE_DEVELOPMENT:{semantic}:{evidence:.3f}"))
    cs=make_changeset(save_uid,checkpoint_id,changes,mode="STAGED_LOCKED") if changes else None
    reasons["BELOW_THRESHOLD_OR_NO_PLUS_ROLE"] = max(0,eligible-len({c[1] for c in candidates}))
    return StagePlan(cs,eligible,len(changes),held_free,reasons)
