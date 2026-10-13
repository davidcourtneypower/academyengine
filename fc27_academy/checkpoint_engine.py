"""Career-checkpoint ingestion for tracked generated players."""
from __future__ import annotations
from .path_history_store import editable_history
from .role_progression_evidence import role_training_signal
from .role_sync import decode_role
from .runtime_config import role_progress_multiplier

# Rebalance future Role evidence without rewriting historical ledgers.
ROLE_PROGRESS_RATE = 3.0

def _clean_role_label(v):
 label=decode_role(v)
 if label.startswith("UNKNOWN") or label=="None": return None
 # 'CB Ball-Playing Defender+' -> 'Ball-Playing Defender'
 core=label.split(" ",1)[1] if " " in label else label
 return core.rstrip("+")

def ingest_checkpoint(tracked, snapshot, *, checkpoint_id, career_date=None):
 # v1.24.10: the caller passes a throwaway view of the player's own structures and
 # assigns the result straight back, so mutate in place instead of deep-copying the
 # whole player (incl. history) for every tracked player (~7s per 7,240 players).
 out=dict(tracked); eng=out.setdefault("engine",{}); hist=out.setdefault("history",[])
 if eng.get("last_checkpoint_id")==checkpoint_id:
  return out,{"status":"IDEMPOTENT_NOOP","checkpoint_id":checkpoint_id}
 before=(out.get("game") or {}).get("attributes",{})
 after=(snapshot or {}).get("attributes",{})
 ledger=eng.setdefault("role_progress",{})
 role_meta=eng.setdefault("role_progress_meta",{})
 for _k,_v in list(ledger.items()):
  try: ledger[_k]=round(min(100.0,max(0.0,float(_v or 0))),3)
  except Exception: ledger[_k]=0.0
 signals={}
 role_cooldown=int(eng.get("role_acquisition_cooldown_days_remaining",0) or 0)
 if role_cooldown<=0:
  for rv in snapshot.get("roles",out.get("game",{}).get("roles",[])):
   name=_clean_role_label(rv)
   # Only Role+ fields can upgrade to Role++; do not retrain completed roles.
   if not name or not 1 <= int(rv or 0) <= 52 or float(ledger.get(name,0) or 0)>=100.0: continue
   raw_sig=role_training_signal(name,before,after,eng.get("football_dna"))
   sig=round(raw_sig*ROLE_PROGRESS_RATE*role_progress_multiplier(),3)
   if sig>0:
    oldv=round(float(ledger.get(name,0) or 0),3)
    newv=round(min(100.0,oldv+sig),3)
    ledger[name]=newv; signals[name]=sig
    meta=role_meta.setdefault(name,{})
    rh=editable_history(meta)
    rh.append({"checkpoint_id":checkpoint_id,"career_date":career_date or {},"from":oldv,"to":newv,"increment":round(newv-oldv,3),"source":"verified_fc27_role_development"})
    if len(rh)>48: del rh[:-48]
    meta["last_increment"]=sig; meta["last_checkpoint_id"]=checkpoint_id; meta["last_career_date"]=career_date or {}
 # Only record checkpoints that produced role evidence; empty entries filled the
 # bounded 96-entry history and the world file with no information.
 if signals: hist.append({"type":"CAREER_CHECKPOINT","checkpoint_id":checkpoint_id,"role_training_signals":signals})
 out["game"]=dict(snapshot); eng["last_checkpoint_id"]=checkpoint_id
 return out,{"status":"INGESTED","checkpoint_id":checkpoint_id,"role_training_signals":signals}
