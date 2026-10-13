"""Observe FC27-native evolution at each checkpoint without writing the game.

This is the evidence layer for later verified attribute, potential and PlayStyle
staging. FC27 remains authoritative for native changes; observations are persisted
in each player's bounded history.
"""
from __future__ import annotations

PLAYSTYLE_FIELDS=("trait1","trait2","icontrait1","icontrait2")

def observe(previous:dict,current:dict):
    prev_attrs=(previous or {}).get("attributes") or {}
    cur_attrs=(current or {}).get("attributes") or {}
    attr_changes={}
    for field,now in cur_attrs.items():
        old=prev_attrs.get(field)
        if isinstance(old,(int,float)) and isinstance(now,(int,float)) and int(now)!=int(old):
            attr_changes[field]=int(now)-int(old)
    old_p=(previous or {}).get("potential"); new_p=(current or {}).get("potential")
    potential_change=None
    if isinstance(old_p,(int,float)) and isinstance(new_p,(int,float)) and int(old_p)!=int(new_p):
        potential_change=int(new_p)-int(old_p)
    ps_changes={}
    for field in PLAYSTYLE_FIELDS:
        old=(previous or {}).get(field); new=(current or {}).get(field)
        if isinstance(old,(int,float)) and isinstance(new,(int,float)) and int(old)!=int(new):
            ps_changes[field]={"from":int(old),"to":int(new),"xor":int(old)^int(new)}
    return {"attribute_changes":attr_changes,"potential_change":potential_change,"playstyle_changes":ps_changes}
