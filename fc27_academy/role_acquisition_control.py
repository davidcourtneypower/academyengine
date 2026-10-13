"""Controlled Role+ -> Role++ production gate.

Role progression is driven only by observed native FC27 attribute development while a
player is attached to a club. Production is conservative: free agents/missing players
cannot win, one semantic Role winner
per player is considered, all matching role fields for that semantic Role are upgraded
atomically, and the path is receipt/cooldown gated.
"""
from __future__ import annotations
from .evolution_staging import ROLE_PLUS_TO_PLUSPLUS_THRESHOLD, _semantic
from .role_sync import ROLE_ID_TO_LABEL
from .runtime_config import role_cooldown_days

COOLDOWN_DAYS = 120


def _field_changes(game:dict, semantic:str):
    out=[]
    for idx,rv in enumerate(list(game.get('roles') or [])[:5],1):
        try: rid=int(rv)
        except (TypeError,ValueError): continue
        if not (1 <= rid <= 52): continue
        if _semantic(rid) != semantic: continue
        target=rid+100
        if rid not in ROLE_ID_TO_LABEL or target not in ROLE_ID_TO_LABEL: continue
        out.append({'field':f'role{idx}','expected':rid,'proposed':target})
    return out


def audit_world(world:dict):
    cooldown_days=role_cooldown_days()
    winners=[]; cooldown_held=[]; suppressed=[]; mapping_holds=[]
    ready_paths=0; ready_players=set()
    for p in (world.get('players') or {}).values():
        if not p.get('observed_this_checkpoint',False) or p.get('lifecycle')!='CLUB':
            continue
        pid=int(p.get('playerid',0)); g=p.get('game') or {}; e=p.get('engine') or {}
        cooldown=int(e.get('role_acquisition_cooldown_days_remaining',0) or 0)
        rows=[]
        for semantic,val in (e.get('role_progress') or {}).items():
            try: prog=float(val)
            except (TypeError,ValueError): continue
            if prog < ROLE_PLUS_TO_PLUSPLUS_THRESHOLD: continue
            changes=_field_changes(g,str(semantic))
            if not changes: continue
            ready_paths += 1; ready_players.add(pid)
            base={'playerid':pid,'role':str(semantic),'progress':round(prog,3),'field_changes':changes,'write_performed':'NO'}
            if cooldown>0:
                base.update(validation='HOLD_ROLE_COOLDOWN',cooldown_days_remaining=cooldown); cooldown_held.append(base); continue
            # Every field must be on the verified 1..52 -> 101..152 FC27 role path.
            valid=all(c['expected'] in ROLE_ID_TO_LABEL and c['proposed'] in ROLE_ID_TO_LABEL and c['proposed']==c['expected']+100 for c in changes)
            if not valid:
                base['validation']='HOLD_ROLE_MAPPING'; mapping_holds.append(base); continue
            # Progress is the ranking signal. Deterministic tie-break by semantic name.
            base.update(score=round(prog,3),validation='READY_ROLE_VERIFIED',cooldown_days_after_apply=cooldown_days,
                        mapping_evidence='FC27_ROLE_1_52_TO_101_152_SAVE_RELOAD_VERIFIED',
                        simulated_progress_after_receipt=0.0,simulated_cooldown_days=cooldown_days,
                        cooldown_starts_on='SUCCESSFUL_WRITE_RECEIPT_ONLY')
            rows.append(base)
        if not rows: continue
        rows.sort(key=lambda r:(-r['score'],r['role']))
        winners.append(rows[0])
        for rank,row in enumerate(rows[1:],2):
            row=dict(row); row['rank']=rank; row['validation']='HOLD_COMPETING_ROLE_PATH'; suppressed.append(row)
    return {
        'mode':'CONTROLLED_ROLE_PRODUCTION','ready_paths':ready_paths,'ready_players':len(ready_players),
        'winner_count':len(winners),'suppressed_competing_paths':len(suppressed),
        'mapping_holds':len(mapping_holds),'cooldown_holds':len(cooldown_held),
        'production_eligible':sum(x.get('validation')=='READY_ROLE_VERIFIED' for x in winners),
        'cooldown_days':cooldown_days,'winners':winners,'verified_candidates':[x for x in winners if x.get('validation')=='READY_ROLE_VERIFIED'],
        'held_cooldown':cooldown_held,'mapping_held':mapping_holds,'suppressed':suppressed,
        'writes_locked':True,'write_performed':False,
    }
