"""Save-aligned Academy Engine checkpoints for the clean v1.24 architecture.

Rollback state is sourced only from the v1.24 SQLite checkpoint journal.
Only checkpoints created by the clean v1.24 architecture are accepted.
"""
from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from pathlib import Path
import json, os, datetime as _dt
from .paths import ACADEMY_STATE_ROOT, EVENTS_ROOT
from .world_bootstrap_store import WorldBootstrapStore
from .transaction_store import create_checkpoint as _db_create_checkpoint, checkpoint_for_date as _db_checkpoint_for_date, clear_events_in_checkpoints

def _safe(v: str) -> str:
    return ''.join(c for c in str(v) if c.isalnum() or c in '-_') or 'UNKNOWN'

def _ordinal(d: dict | None):
    if not isinstance(d, dict): return None
    try: return _dt.date(int(d['year']), int(d['month']), int(d['day'])).toordinal()
    except Exception: return None

def _events_path(storage_key: str) -> Path:
    return EVENTS_ROOT / _safe(storage_key) / 'events.json'

def _read_json(path: Path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding='utf-8')
    replace_retry(tmp, path)

def create_restore_point(storage_key: str, *, trigger: str = 'CHECKPOINT', request_id: str = '') -> dict:
    key = str(storage_key or '').strip()
    if not key: return {'status':'SKIP','reason':'NO_STORAGE_KEY'}
    wp = WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(key)
    if not wp.exists(): return {'status':'SKIP','reason':'WORLD_MISSING'}
    world = _read_json(wp, {})
    events = _read_json(_events_path(key), {'schema':1,'events':[]})
    return _db_create_checkpoint(
        key, world=world, events=events, trigger=str(trigger or 'CHECKPOINT'), request_id=str(request_id or ''),
        career_uid=str(world.get('career_uid') or ''), branch_id=str(world.get('branch_id') or ''),
    )

def restore_for_date(source_key: str, target_key: str, career_date: dict | None) -> dict:
    """Restore to the newest v1.24 SQLite checkpoint not later than FC27's loaded save date."""
    src=str(source_key or '').strip(); dst=str(target_key or '').strip(); target_ord=_ordinal(career_date)
    if not src or not dst or target_ord is None:return {'status':'MISS','reason':'INVALID_TARGET'}
    row=_db_checkpoint_for_date(src,career_date)
    if not row:return {'status':'MISS','reason':'NO_V124_CHECKPOINT','target_ordinal':target_ord}
    world=dict(row.get('world') or {}); events=dict(row.get('events') or {'schema':1,'events':[]})
    restored=int(row.get('date_ordinal') or 0); trigger=row.get('trigger')
    world['storage_key']=dst; world['save_uid']=dst
    for e in events.get('events') or []:
        if isinstance(e,dict): e['storage_key']=dst
    wp=WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(dst)
    _write_json(wp,world); _write_json(_events_path(dst),events)
    _db_create_checkpoint(dst,world=world,events=events,trigger='LOAD_RECONCILED',request_id='',career_uid=str(world.get('career_uid') or ''),branch_id=str(world.get('branch_id') or ''))
    return {'status':'RESTORED','source_storage_key':src,'source':'sqlite','restored_ordinal':restored,'target_ordinal':target_ord,'exact_date':restored==target_ord,'trigger':trigger}

def clear_event_history_from_restore_points(storage_key: str) -> int:
    key=str(storage_key or '').strip()
    return clear_events_in_checkpoints(key) if key else 0
