"""Role progression from observed FC27 development.

Training is deliberately not guessed from a hidden plan field. If FC27 training changes
relevant attributes, the next snapshot records those real deltas and they become role
progress evidence. This makes training influential without depending on an unverified API.
"""
from __future__ import annotations
from .football_dna_v2 import GROUP_ATTRS

ROLE_GROUPS={
 "Goalkeeper":("goalkeeping","mentality"), "Sweeper Keeper":("goalkeeping","passing","mentality"),
 "Ball-Playing Keeper":("goalkeeping","passing","mentality"), "Defender":("defending","physical","mentality"),
 "Stopper":("defending","physical","mentality"), "Ball-Playing Defender":("defending","passing","mentality"),
 "Fullback":("defending","pace","physical"), "Wingback":("pace","passing","physical"),
 "Attacking Wingback":("pace","passing","technique"), "Inverted Wingback":("passing","technique","mentality"),
 "Holding":("defending","mentality","passing"), "Centre Half":("defending","physical","mentality"),
 "Deep-Lying Playmaker":("passing","technique","mentality"), "Box-to-Box":("physical","passing","mentality"),
 "Box Crasher":("physical","shooting","mentality"), "Playmaker":("passing","technique","mentality"),
 "Classic 10":("passing","technique","flair"), "Winger":("pace","technique","passing"),
 "Wide Playmaker":("passing","technique","flair"), "Inside Forward":("pace","shooting","technique"),
 "Advanced Forward":("shooting","pace","technique"), "Poacher":("shooting","mentality","pace"),
 "False 9":("passing","technique","shooting"), "Target Forward":("physical","shooting","mentality"),
 "Roaming Striker":("shooting","pace","mentality"),
 # v1.24.10: roles that previously had no evidence groups and could never progress.
 "Falseback":("defending","passing","mentality"), "Wide Half":("passing","defending","physical"),
 "Half-Winger":("passing","technique","pace"), "Half Winger":("passing","technique","pace"),
 "Wide Midfielder":("pace","passing","physical"), "Shadow Striker":("shooting","technique","mentality"),
 "Wide Back":("defending","pace","physical"), "False Winger":("technique","passing","flair"),
}

# GROUP_ATTRS (used for DNA inference) has no "flair" group, so roles listing flair
# only ever counted two of their three groups. Role evidence gets its own flair set;
# DNA inference is deliberately left unchanged so existing players keep their DNA.
ROLE_GROUP_ATTRS=dict(GROUP_ATTRS)
ROLE_GROUP_ATTRS["flair"]=["dribbling","agility","balance","curve","ballcontrol"]

def attribute_deltas(before,after):
 return {k:int(after[k])-int(v) for k,v in before.items() if k in after and isinstance(v,(int,float)) and isinstance(after[k],(int,float))}

def role_training_signal(role_name,before,after,dna=None):
 groups=ROLE_GROUPS.get(role_name,())
 deltas=attribute_deltas(before,after); weighted=[]
 apt=(dna or {}).get("aptitudes",{})
 for g in groups:
  fields=ROLE_GROUP_ATTRS.get(g,())
  vals=[max(0,deltas.get(f,0)) for f in fields if f in deltas]
  if vals: weighted.append((sum(vals)/len(vals))*float(apt.get(g,1.0)))
 raw=sum(weighted)/len(weighted) if weighted else 0.0
 # Bounded checkpoint signal; actual Role+/++ unlock remains a separate threshold decision.
 return round(max(0.0,min(3.0,raw)),3)
