from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from pathlib import Path
import json, os, time, uuid, hashlib
from .paths import EVENTS_ROOT, ACADEMY_STATE_ROOT
from .world_bootstrap_store import WorldBootstrapStore
from .playstyle_lifetime import current_styles, normal_cap

EVENT_SCHEMA = 1


def _safe(v: str) -> str:
    return ''.join(c for c in str(v) if c.isalnum() or c in '-_') or 'UNKNOWN'


def _path(storage_key: str) -> Path:
    return EVENTS_ROOT / _safe(storage_key) / 'events.json'


def _atomic(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding='utf-8')
    replace_retry(tmp, path)


def load_events(storage_key: str) -> list[dict]:
    p = _path(storage_key)
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
        return list(obj.get('events') or [])
    except Exception:
        return []


def append_event(storage_key: str, event: dict) -> dict:
    p = _path(storage_key)
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        obj = {'schema': EVENT_SCHEMA, 'events': []}
    row = {
        'event_id': event.get('event_id') or ('evt_' + uuid.uuid4().hex),
        'created_at': int(time.time()),
        'read': bool(event.get('read', False)),
        **event,
    }
    obj['schema'] = EVENT_SCHEMA
    events = obj.setdefault('events', [])
    if not any(e.get('event_id') == row['event_id'] for e in events):
        events.append(row)
    if len(events) > 600:
        del events[:-600]
    _atomic(p, obj)
    return row


def mark_all_read(storage_key: str) -> None:
    p = _path(storage_key)
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return
    changed = False
    for e in obj.get('events') or []:
        if not e.get('read'):
            e['read'] = True
            changed = True
    if changed:
        _atomic(p, obj)


def _world(storage_key: str) -> dict:
    p = WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(storage_key)
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}


def record_native_role_upgrades(storage_key: str, upgrades: list, career: dict | None = None) -> list[dict]:
    """Events for Role+ -> Role++ upgrades FC27 made itself (v1.24.26)."""
    career = career or {}
    user_teamid = career.get('user_teamid')
    out = []
    for u in upgrades or []:
        pid = int(u.get('playerid') or 0)
        identity = f"{storage_key}|FC27_NATIVE_ROLE|{pid}|{u.get('role_id')}"
        out.append(append_event(storage_key, {
            'event_id': 'evt_' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24],
            'type': 'ROLE_UPGRADED', 'title': 'Upgraded by FC27', 'source': 'FC27',
            'playerid': pid, 'player_name': u.get('player_name') or f'Generated Player #{pid}',
            'club_name': u.get('club_name') or '', 'position': u.get('position'), 'age': u.get('age'),
            'overall': u.get('overall'), 'value': str(u.get('role') or ''), 'importance': 'MEDIUM',
            'career_date': dict(career.get('date') or {}), 'storage_key': storage_key,
            'is_user_team': bool(user_teamid not in (None, '', 0, '0') and u.get('clubteamid') == user_teamid),
            'read': False,
        }))
    return out


def record_commit(storage_key: str, commit: dict) -> list[dict]:
    """Convert a committed engine transaction into user-facing football events."""
    if not commit or commit.get('status') != 'COMMITTED':
        return []
    world = _world(storage_key)
    career = world.get('career') or {}
    user_teamid = career.get('user_teamid')
    current_date = career.get('date') or {}
    out = []
    for c in commit.get('committed') or []:
        pid = str(int(c.get('playerid', 0)))
        player = (world.get('players') or {}).get(pid) or {}
        game = player.get('game') or {}
        name = game.get('name') or f"Generated Player #{pid}"
        club = game.get('clubname') or career.get('team_name') or ''
        kind = c.get('kind')
        if kind == 'NORMAL_ACQUISITION':
            etype, title, detail, importance = 'PLAYSTYLE_GAINED', 'PlayStyle Acquired', str(c.get('style') or ''), 'HIGH'
        elif kind == 'PLUS_ACQUISITION':
            etype, title, detail, importance = 'PLAYSTYLE_PLUS_GAINED', 'PlayStyle+ Acquired', str(c.get('style') or ''), 'CRITICAL'
        elif kind == 'ROLE_UPGRADE':
            etype, title, detail, importance = 'ROLE_UPGRADED', 'Role++ Acquired', str(c.get('role') or ''), 'HIGH'
        elif kind == 'PLAYSTYLE_LOSS':
            # v1.24.36: PlayStyle decline with age.
            etype, title, detail, importance = 'PLAYSTYLE_LOST', 'PlayStyle Lost', str(c.get('style') or ''), 'HIGH'
        elif kind == 'PLUS_DOWNGRADE':
            st = str(c.get('style') or '')
            etype, title, importance = 'PLAYSTYLE_PLUS_DOWNGRADED', 'PlayStyle+ Downgraded', 'HIGH'
            detail = f'{st}+ → {st}' if c.get('added_normal') or st in current_styles(game)[0] else f'{st}+'
        elif kind == 'NEWGEN_ENRICHMENT':
            # v1.24.12: starting PlayStyles assigned by Academy Engine to a player it sees
            # for the first time (new generation, or a youth player promoted into a club
            # squad) were committed silently. Record them like any other acquisition.
            etype, title, detail, importance = 'PLAYSTYLE_GAINED', 'Starting PlayStyles assigned', str(c.get('style') or ''), 'MEDIUM'
        else:
            continue
        changeset = str(commit.get('changeset_id') or '')
        identity = f"{storage_key}|{changeset}|{pid}|{kind}|{detail}"
        event_id = 'evt_' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]
        row = append_event(storage_key, {
            'event_id': event_id,
            'type': etype,
            'title': title,
            'playerid': int(pid),
            'player_name': name,
            'club_name': club,
            'position': game.get('preferredposition1'),
            'age': game.get('age'),
            'overall': game.get('overallrating'),
            'value': detail,
            'importance': importance,
            'career_date': current_date,
            'changeset_id': changeset,
            'storage_key': storage_key,
            'is_user_team': bool(user_teamid not in (None,'',0,'0') and game.get('clubteamid') == user_teamid),
            'read': False,
            **({'cap_before': c.get('cap_before'), 'cap_after': c.get('cap_after')} if kind in ('PLAYSTYLE_LOSS', 'PLUS_DOWNGRADE') else {}),
        })
        out.append(row)
        if kind == 'NORMAL_ACQUISITION':
            normal, _, _ = current_styles(game)
            cap = normal_cap(player)
            if len(normal) + 1 >= cap:
                cap_identity = f"{storage_key}|{changeset}|{pid}|PLAYER_REACHED_CAP|{cap}"
                out.append(append_event(storage_key, {
                    'event_id':'evt_' + hashlib.sha256(cap_identity.encode('utf-8')).hexdigest()[:24],
                    'type':'PLAYER_REACHED_CAP','title':'Lifetime PlayStyle profile complete',
                    'playerid':int(pid),'player_name':name,'club_name':club,
                    'position':game.get('preferredposition1'),'age':game.get('age'),'overall':game.get('overallrating'),
                    'value':f'{cap} / {cap} PlayStyles','importance':'MEDIUM','career_date':current_date,
                    'storage_key':storage_key,'is_user_team': bool(user_teamid not in (None,'',0,'0') and game.get('clubteamid') == user_teamid),'read':False,
                }))
    return out


def clear_events(storage_key: str) -> None:
    if not storage_key: return
    _atomic(_path(storage_key), {'schema': EVENT_SCHEMA, 'events': []})
