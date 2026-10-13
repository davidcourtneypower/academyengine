"""Controlled PlayStyle+ production candidate selection.

A style may upgrade to + only when the normal PlayStyle is already present, its
persistent + ledger reaches the configured threshold, the player is not on the
separate + cooldown, and the style remains football-plausible for the player.
"""
from __future__ import annotations
from .playstyle_development_planner import current_styles
from .runtime_config import plus_threshold, plus_cooldown_days
from .playstyle_acquisition_control import _fit
from .playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK, verified_mapping, mapping_evidence
from .playstyle_lifetime import plus_addition_slots, ensure_policy, ENGINE_PLUS_CAP

PLUS_COOLDOWN_DAYS=180  # default export

def _target(game, style):
    is_gk=int(game.get('preferredposition1',-1))==0
    mapping=PLAYSTYLE2_GK if is_gk else PLAYSTYLE1
    bit=mapping.get(style)
    field='icontrait2' if is_gk else 'icontrait1'
    if bit is None: return None
    cur=int(game.get(field,0) or 0)
    return field,cur,cur|int(bit),int(bit)

def audit_world(world):
    threshold=plus_threshold(); cooldown_days=plus_cooldown_days()
    winners=[]; suppressed=[]; held_plausibility=[]; held_cooldown=[]; held_lifetime=[]
    ready_paths=0; ready_players=set()
    for p in (world.get('players') or {}).values():
        if not p.get('observed_this_checkpoint',False) or p.get('lifecycle')!='CLUB': continue
        g=p.get('game') or {}; e=p.get('engine') or {}; ensure_policy(p)
        normal,plus,_=current_styles(g)
        plus_slots=plus_addition_slots(p)
        cooldown=int(e.get('playstyle_plus_cooldown_days_remaining',0) or 0)
        rows=[]
        for style,val in (e.get('playstyle_plus_progress') or {}).items():
            try: prog=float(val)
            except (TypeError,ValueError): continue
            if prog < threshold or style not in normal or style in plus: continue
            ready_paths+=1; ready_players.add(int(p.get('playerid',0)))
            if plus_slots<=0:
                held_lifetime.append({'playerid':int(p.get('playerid',0)),'style':str(style),'progress':round(prog,3),'validation':'HOLD_PLUS_LIFETIME_ELIGIBILITY','plus_count':len(plus),'plus_cap':ENGINE_PLUS_CAP,'plus_eligible':bool(e.get('playstyle_plus_lifetime_eligible',False))})
                continue
            if cooldown>0:
                held_cooldown.append({'playerid':int(p.get('playerid',0)),'style':str(style),'progress':round(prog,3),'validation':'HOLD_PLUS_COOLDOWN','cooldown_days_remaining':cooldown})
                continue
            attr_fit,dna_fit,matched,fit_score,plausibility=_fit(p,style)
            base={'playerid':int(p.get('playerid',0)),'style':str(style),'progress':round(prog,3),'attribute_fit':attr_fit,'dna_fit':dna_fit,'matched_positions':matched,'plausibility':plausibility,'write_performed':'NO'}
            if plausibility=='INSUFFICIENT_ATYPICAL_EVIDENCE':
                base['validation']='HOLD_PLAUSIBILITY'; held_plausibility.append(base); continue
            t=_target(g,style)
            verified=bool(t and verified_mapping(t[0],t[3]))
            base.update(score=round(prog+fit_score,3),target=t,verified=verified)
            rows.append(base)
        if not rows: continue
        rows.sort(key=lambda r:(-r['score'],-r['attribute_fit'],-r['dna_fit'],r['style']))
        win=rows[0]; t=win.pop('target'); verified=win.pop('verified')
        win['rank']=1; win['operation']='ADD_PLUS_BIT'; win['cooldown_days_after_apply']=cooldown_days
        if t:
            win.update(field=t[0],expected=t[1],proposed=t[2],bit=t[3],already_owned_bit=bool(int(t[1]) & int(t[3])))
            win['mapping_name']=verified_mapping(t[0],t[3]); win['mapping_evidence']=mapping_evidence(t[0],t[3])
            win['simulated_post_value']=t[2]; win['simulated_progress_after_receipt']=0.0; win['simulated_cooldown_days']=cooldown_days
        else:
            win.update(field=None,expected=None,proposed=None,bit=None,already_owned_bit=False,mapping_name=None,mapping_evidence=None)
        win['validation']='READY_PLUS_VERIFIED' if verified else 'HOLD_MAPPING'; winners.append(win)
        for rank,row in enumerate(rows[1:],2):
            row.pop('target',None); row.pop('verified',None); row['rank']=rank; row['validation']='HOLD_COMPETING_PLUS_PATH'; suppressed.append(row)
    verified=sum(x['validation']=='READY_PLUS_VERIFIED' for x in winners)
    return {
        'mode':'PLAYSTYLE_PLUS_PRODUCTION_GATE',
        'ready_paths':ready_paths,'ready_players':len(ready_players),
        'winner_count':len(winners),'suppressed_competing_paths':len(suppressed),
        'plausibility_holds':len(held_plausibility),'cooldown_holds':len(held_cooldown),
        'mapping_holds':sum(x['validation']=='HOLD_MAPPING' for x in winners),
        'lifetime_eligibility_holds':len(held_lifetime),
        'production_eligible':verified,'cooldown_days':cooldown_days,
        'winners':winners,'verified_candidates':[x for x in winners if x['validation']=='READY_PLUS_VERIFIED'],
        'held_plausibility':held_plausibility,'held_cooldown':held_cooldown,'held_lifetime':held_lifetime,'suppressed':suppressed,
        'writes_locked':True,'write_performed':False,
    }
