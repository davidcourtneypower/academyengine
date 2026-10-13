"""Staged FC27 synchronisation boundary.

Produces deterministic changesets only from FC27-verified write families. The normal
production path is fail-closed: save UID, generated-player ID, expected-old-value,
field whitelist, immediate readback and transaction rollback are mandatory.
No changeset is applied merely because it was proposed.
"""
from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from dataclasses import dataclass, asdict
from pathlib import Path
import json, os, uuid

OUTFIELD=("crossing","finishing","headingaccuracy","shortpassing","volleys","defensiveawareness","standingtackle","slidingtackle","dribbling","curve","freekickaccuracy","longpassing","ballcontrol","shotpower","jumping","stamina","strength","longshots","acceleration","sprintspeed","agility","reactions","balance","aggression","composure","interceptions","positioning","vision","penalties")
GK=("gkdiving","gkhandling","gkkicking","gkpositioning","gkreflexes")
ROLES=tuple(f"role{i}" for i in range(1,6))
from .playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK, verified_mapping, normal_mapping, plus_mapping

class StageError(ValueError): pass

@dataclass(frozen=True)
class Change:
    player_id:int; field:str; expected:int; target:int; family:str; reason:str

@dataclass(frozen=True)
class ChangeSet:
    changeset_id:str; save_uid:str; checkpoint_id:str; mode:str; changes:tuple[Change,...]

def _valid_role(v): return v==0 or 1<=v<=52 or 101<=v<=152

def validate_change(c:Change):
    if c.player_id < 460000: raise StageError('generated-player guard')
    if c.expected==c.target: raise StageError('no-op change')
    if c.family in ('OUTFIELD_ATTRIBUTE','GK_ATTRIBUTE','POTENTIAL'):
        raise StageError('write family disabled: FC27 owns attributes/ageing and Dynamic Potential')
    elif c.family=='ROLE':
        if c.field not in ROLES or not _valid_role(c.expected) or not _valid_role(c.target): raise StageError('invalid role')
    elif c.family in ('PLAYSTYLE','PLAYSTYLE_PLUS','PLAYSTYLE_SET'):
        if c.field not in ('trait1','trait2','icontrait1','icontrait2'): raise StageError('invalid playstyle field')
        diff=c.expected ^ c.target
        if diff<=0: raise StageError('playstyle no-bit change')
        # Production writes are additive only. Removing/toggling an existing bit is never
        # a valid Academy Engine acquisition transaction.
        if c.expected & diff or c.target != (c.expected | diff): raise StageError('playstyle write must add previously absent bit(s)')
        if c.family=='PLAYSTYLE_SET':
            if c.field.startswith('icontrait'): raise StageError('starting set requires normal trait field')
            # Newgen starting richness can safely add several source-verified normal
            # PlayStyle bits in one exact field write. Every individual bit must be known.
            remaining=diff
            while remaining:
                bit=remaining & -remaining
                if verified_mapping(c.field,bit) is None or normal_mapping(c.field,bit) is None:
                    raise StageError('unverified playstyle bit in set')
                remaining -= bit
        else:
            if diff&(diff-1): raise StageError('playstyle must alter one bit')
            if verified_mapping(c.field,diff) is None: raise StageError('unverified playstyle bit')
            if c.family=='PLAYSTYLE_PLUS':
                if not c.field.startswith('icontrait'): raise StageError('plus requires icontrait')
                if plus_mapping(c.field,diff) is None: raise StageError('unverified playstyle+ mapping')
            if c.family=='PLAYSTYLE':
                if c.field.startswith('icontrait'): raise StageError('normal requires trait')
                if normal_mapping(c.field,diff) is None: raise StageError('unverified normal playstyle mapping')
    elif c.family in ('PLAYSTYLE_LOSS','PLAYSTYLE_PLUS_LOSS'):
        # v1.24.36: PlayStyle decline. Exactly one known PlayStyle bit is cleared and
        # nothing else in the field changes. Normal loss -> trait field, PlayStyle+ -> icontrait.
        if c.field not in ('trait1','trait2','icontrait1','icontrait2'): raise StageError('invalid playstyle field')
        diff=c.expected ^ c.target
        if diff<=0 or diff&(diff-1): raise StageError('playstyle loss must clear exactly one bit')
        if not (c.expected & diff) or c.target != (c.expected & ~diff): raise StageError('playstyle loss must clear a present bit only')
        if c.family=='PLAYSTYLE_LOSS' and c.field.startswith('icontrait'): raise StageError('normal loss requires trait field')
        if c.family=='PLAYSTYLE_PLUS_LOSS' and not c.field.startswith('icontrait'): raise StageError('plus loss requires icontrait field')
        known=set(PLAYSTYLE1.values()) if c.field.endswith('1') else set(PLAYSTYLE2_GK.values())
        if diff not in known: raise StageError('unknown playstyle bit')
    else: raise StageError('unverified write family')
    return True

def make_changeset(save_uid,checkpoint_id,changes,mode='STAGED_LOCKED'):
    if not str(save_uid).strip(): raise StageError('save_uid required')
    cs=ChangeSet(uuid.uuid4().hex,str(save_uid),str(checkpoint_id),mode,tuple(changes))
    seen=set()
    for c in cs.changes:
        validate_change(c); key=(c.player_id,c.field)
        if key in seen: raise StageError('duplicate player/field')
        seen.add(key)
    return cs

def write_changeset(cs:ChangeSet,root):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    obj=asdict(cs); obj['schema']=1; obj['writes_locked']=cs.mode!='APPLY_VERIFIED'
    tmp=root/(cs.changeset_id+'.json.tmp'); final=root/(cs.changeset_id+'.json')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True),encoding='utf-8'); replace_retry(tmp,final)
    return final
