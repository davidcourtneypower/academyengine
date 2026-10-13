from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from fc27_academy.paths import CACHE_ROOT, ACADEMY_STATE_ROOT

DB_PATH = CACHE_ROOT / 'academy_read_model.sqlite3'

SORT_COLUMNS = {
    0: 'name COLLATE NOCASE', 1: 'club COLLATE NOCASE', 2: 'position COLLATE NOCASE',
    3: 'age', 4: 'ovr', 5: 'potential', 6: 'normal_count', 7: 'next_ps COLLATE NOCASE',
    8: 'next_ps_pct', 9: 'plus_eligible', 10: 'next_plus COLLATE NOCASE',
    11: 'next_plus_pct', 12: 'roles_count', 13: 'next_role COLLATE NOCASE', 14: 'role_progress_pct',
}


def _fold(value):
    """Accent/case-insensitive search key: 'Müller' and 'muller' both -> 'muller' (v1.24.10)."""
    import unicodedata
    text=unicodedata.normalize('NFKD',str(value or ''))
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold().replace('ø','o').replace('đ','d').replace('ł','l').replace('ß','ss').replace('æ','ae').replace('œ','oe')


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    try: con.create_function('fold',1,_fold,deterministic=True)
    except Exception: pass
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=NORMAL')
    con.execute('PRAGMA temp_store=MEMORY')
    _ensure_schema(con)
    return con


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript('''
    CREATE TABLE IF NOT EXISTS career_cache (
        storage_key TEXT PRIMARY KEY,
        world_mtime_ns INTEGER NOT NULL DEFAULT 0,
        world_size INTEGER NOT NULL DEFAULT 0,
        rebuilt_at REAL NOT NULL DEFAULT 0,
        player_count INTEGER NOT NULL DEFAULT 0,
        team_name TEXT NOT NULL DEFAULT '',
        season TEXT NOT NULL DEFAULT '',
        date_text TEXT NOT NULL DEFAULT '',
        unresolved_names INTEGER NOT NULL DEFAULT 0,
        payload_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS players (
        storage_key TEXT NOT NULL,
        playerid INTEGER NOT NULL,
        name TEXT NOT NULL,
        club TEXT NOT NULL,
        position TEXT NOT NULL,
        age INTEGER,
        ovr INTEGER,
        potential INTEGER,
        normal_count INTEGER NOT NULL DEFAULT 0,
        plus_count INTEGER NOT NULL DEFAULT 0,
        roles_count INTEGER NOT NULL DEFAULT 0,
        cap INTEGER NOT NULL DEFAULT 7,
        next_ps TEXT NOT NULL DEFAULT '',
        next_ps_pct REAL NOT NULL DEFAULT 0,
        next_plus TEXT NOT NULL DEFAULT '',
        next_plus_pct REAL NOT NULL DEFAULT 0,
        role_progress_pct REAL NOT NULL DEFAULT 0,
        status_text TEXT NOT NULL DEFAULT '',
        plus_eligible INTEGER NOT NULL DEFAULT 0,
        is_user_team INTEGER NOT NULL DEFAULT 0,
        lifecycle TEXT NOT NULL DEFAULT '',
        playstyles_text TEXT NOT NULL DEFAULT '',
        roles_text TEXT NOT NULL DEFAULT '',
        json_blob TEXT NOT NULL,
        PRIMARY KEY(storage_key, playerid)
    );
    CREATE INDEX IF NOT EXISTS idx_players_scope ON players(storage_key, is_user_team);
    CREATE INDEX IF NOT EXISTS idx_players_ovr ON players(storage_key, ovr);
    CREATE INDEX IF NOT EXISTS idx_players_pot ON players(storage_key, potential);
    CREATE INDEX IF NOT EXISTS idx_players_age ON players(storage_key, age);
    CREATE INDEX IF NOT EXISTS idx_players_pos ON players(storage_key, position);
    CREATE INDEX IF NOT EXISTS idx_players_ps ON players(storage_key, normal_count);
    ''')
    # v1.24.25: sortable Next Role column (highest-progress Role++ path of a current role).
    try: con.execute("ALTER TABLE players ADD COLUMN next_role TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError: pass
    con.execute('CREATE INDEX IF NOT EXISTS idx_players_playstyles_text ON players(storage_key, playstyles_text)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_players_roles_text ON players(storage_key, roles_text)')
    con.commit()


def world_revision(storage_key: str) -> tuple[str, int, int] | None:
    if not storage_key:
        return None
    p = ACADEMY_STATE_ROOT / 'saves' / storage_key / 'generated_world.json'
    try:
        st = p.stat()
        return storage_key, int(st.st_mtime_ns), int(st.st_size)
    except Exception:
        return None


def cached_revision(storage_key: str) -> tuple[str, int, int] | None:
    if not storage_key:
        return None
    with _connect() as con:
        r = con.execute('SELECT world_mtime_ns, world_size FROM career_cache WHERE storage_key=?', (storage_key,)).fetchone()
    return (storage_key, int(r['world_mtime_ns']), int(r['world_size'])) if r else None


def is_stale(storage_key: str) -> bool:
    live = world_revision(storage_key)
    cached = cached_revision(storage_key)
    return bool(live and live != cached)


def _next_role_name(r: dict[str, Any]) -> str:
    roles = r.get('active_role_progress')
    if roles is None: roles = r.get('role_progress') or {}
    best = ('', 0.0)
    for k, v in (roles or {}).items():
        try: fv = float(v or 0)
        except Exception: fv = 0.0
        if fv > best[1]: best = (str(k), fv)
    return best[0]


def sync_world(storage_key: str, world: dict[str, Any], rows: list[dict[str, Any]], date_text: str = '') -> dict[str, Any]:
    rev = world_revision(storage_key) or (storage_key, 0, 0)
    career = world.get('career') or {}
    unresolved = sum(1 for r in rows if str(r.get('name') or '').startswith('Generated Player #'))
    now = time.time()
    payload = {
        'career_uid': world.get('career_uid') or '',
        'branch_id': world.get('branch_id') or '',
        'storage_key': storage_key,
        'user_teamid': career.get('user_teamid'),
        'team_name': career.get('team_name') or '',
        'season': career.get('season') or '',
        'date': career.get('date') or {},
        'season_epoch': world.get('season_epoch', 0),
    }
    values = []
    for r in rows:
        def _int(v):
            try: return int(v)
            except Exception: return None
        values.append((
            storage_key, int(r.get('playerid') or 0), str(r.get('name') or ''), str(r.get('club') or ''),
            str(r.get('position') or ''), _int(r.get('age')), _int(r.get('ovr')), _int(r.get('potential')),
            int(r.get('normal_count') or 0), int(r.get('plus_count') or 0), len(r.get('roles') or []), int(r.get('cap')) if r.get('cap') is not None else 7, str(r.get('next_ps') or ''),
            float(r.get('next_ps_pct') or 0), str(r.get('next_plus') or ''), float(r.get('next_plus_pct') or 0),
            min(100.0,max([float(v or 0) for v in (r.get('active_role_progress',r.get('role_progress')) or {}).values()] or [0.0])), str(r.get('status') or r.get('next_ps_status') or ''),
            1 if r.get('plus_eligible') else 0, 1 if r.get('is_user_team') else 0,
            str(r.get('lifecycle') or ''),
            '|'+'|'.join(sorted({str(x).strip().lower() for x in ((r.get('normal_styles') or [])+(r.get('plus_styles') or [])) if str(x).strip()}))+'|',
            '|'+'|'.join(sorted({str(x).strip().lower() for x in (r.get('roles') or []) if str(x).strip()}))+'|',
            # v1.24.13: the full world entry ('raw', ~12 KB/player) is not cached; the
            # overlay reads it from the world for the one selected player instead.
            json.dumps({k: v for k, v in r.items() if k != 'raw'}, ensure_ascii=False, separators=(',', ':')),
            # next_role is the last table column (added by ALTER TABLE), so it stays last
            # here to keep the unchanged-row comparison with SELECT * exact.
            _next_role_name(r),
        ))
    with _connect() as con:
        con.execute('BEGIN IMMEDIATE')
        existing={int(row['playerid']):tuple(row) for row in con.execute('SELECT * FROM players WHERE storage_key=?',(storage_key,))}
        incoming={row[1] for row in values}
        changed=[row for row in values if existing.get(row[1])!=row]
        removed=[(storage_key,pid) for pid in existing.keys()-incoming]
        con.executemany('DELETE FROM players WHERE storage_key=? AND playerid=?',removed)
        con.executemany('''INSERT OR REPLACE INTO players(
            storage_key,playerid,name,club,position,age,ovr,potential,normal_count,plus_count,roles_count,cap,next_ps,next_ps_pct,next_plus,next_plus_pct,role_progress_pct,status_text,
            plus_eligible,is_user_team,lifecycle,playstyles_text,roles_text,json_blob,next_role) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', changed)
        con.execute('''INSERT INTO career_cache(storage_key,world_mtime_ns,world_size,rebuilt_at,player_count,team_name,season,date_text,unresolved_names,payload_json)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(storage_key) DO UPDATE SET world_mtime_ns=excluded.world_mtime_ns,world_size=excluded.world_size,
            rebuilt_at=excluded.rebuilt_at,player_count=excluded.player_count,team_name=excluded.team_name,season=excluded.season,
            date_text=excluded.date_text,unresolved_names=excluded.unresolved_names,payload_json=excluded.payload_json''',
            (storage_key, rev[1], rev[2], now, len(values), str(career.get('team_name') or ''), str(career.get('season') or ''), date_text, unresolved, json.dumps(payload)))
        con.commit()
    return {'storage_key': storage_key, 'player_count': len(values), 'unresolved_names': unresolved, 'rebuilt_at': now, 'revision': rev, 'rows_written':len(changed), 'rows_deleted':len(removed)}


def career_meta(storage_key: str) -> dict[str, Any]:
    if not storage_key:
        return {}
    with _connect() as con:
        r = con.execute('SELECT * FROM career_cache WHERE storage_key=?', (storage_key,)).fetchone()
    if not r:
        return {}
    d = dict(r)
    try: d.update(json.loads(d.pop('payload_json') or '{}'))
    except Exception: d.pop('payload_json', None)
    return d


def _filters_sql(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    where = ['storage_key=?']
    args: list[Any] = [filters.get('storage_key') or '']
    if filters.get('myclub'): where.append('is_user_team=1')
    pos = str(filters.get('position') or '').strip()
    if pos and pos.lower() != 'all positions':
        poses=[x.strip() for x in pos.split(',') if x.strip() and x.strip().lower()!='all positions']
        if poses:
            where.append('position IN ('+','.join('?' for _ in poses)+')'); args.extend(poses)
    state = filters.get('state')
    if state == 'Developing a PlayStyle': where.append("next_ps<>'' AND next_ps_pct>0")
    elif state == 'Developing a PlayStyle+': where.append("next_plus<>'' AND next_plus_pct>0")
    elif state == 'Developing a Role++': where.append('role_progress_pct>0 AND role_progress_pct<100')
    elif state in ('At lifetime PlayStyle cap', 'At lifetime cap'): where.append('normal_count>=cap')
    elif state == 'Declining': where.append("status_text LIKE '%Decline phase active%'")
    # v1.24.28: OVR / POT accept several ranges ("60-64,65-69,80+"); otherwise min/max.
    ranged=set()
    for col, key in (('ovr','ovr_ranges'),('potential','pot_ranges')):
        parts=[x.strip() for x in str(filters.get(key) or '').split(',') if x.strip() and not x.strip().lower().startswith('any')]
        conds=[]
        for part in parts:
            try:
                if part.endswith('+'): conds.append(f'{col}>=?'); args.append(int(part[:-1]))
                elif '-' in part:
                    lo,hi=part.split('-',1); conds.append(f'({col}>=? AND {col}<=?)'); args.extend([int(lo),int(hi)])
            except ValueError: continue
        if conds: where.append('('+' OR '.join(conds)+')'); ranged.add(col)
    for col, key_min, key_max in [('ovr','ovr_min','ovr_max'),('potential','pot_min','pot_max'),('age','age_min','age_max')]:
        if col in ranged: continue
        lo = int(filters.get(key_min) or 0); hi = int(filters.get(key_max) or 0)
        if lo: where.append(f'{col}>=?'); args.append(lo)
        if hi: where.append(f'{col}<=?'); args.append(hi)
    psmin = int(filters.get('ps_min') or 0)
    if psmin: where.append('normal_count>=?'); args.append(psmin)
    plus_filter = str(filters.get('plus_filter') or 'Any PlayStyle+ Status').strip()
    if plus_filter in ('PlayStyle+ eligible', 'Eligible'): where.append('plus_eligible=1 AND plus_count=0')
    elif plus_filter in ('Not PlayStyle+ eligible', 'Not eligible'): where.append('plus_eligible=0')
    elif plus_filter == 'Has PlayStyle+': where.append('plus_count>0')
    ps = str(filters.get('playstyle') or '').strip().lower()
    if ps and ps != 'any playstyle':
        vals=[x.strip() for x in ps.split(',') if x.strip() and x.strip()!='any playstyle']
        if vals:
            where.append('('+' OR '.join('playstyles_text LIKE ?' for _ in vals)+')'); args.extend([f'%|{x}|%' for x in vals])
    role = str(filters.get('role') or '').strip().lower()
    if role and role != 'any role':
        vals=[x.strip() for x in role.split(',') if x.strip() and x.strip()!='any role']
        if vals:
            where.append('('+' OR '.join('roles_text LIKE ?' for _ in vals)+')'); args.extend([f'%|{x}|%' for x in vals])
    q = _fold(str(filters.get('query') or '').strip())
    if q:
        terms=[x.strip() for x in q.split(',') if x.strip()]
        groups=[]
        for term in terms[:12]:
            like=f'%{term}%'
            groups.append("(fold(name) LIKE ? OR fold(club) LIKE ? OR position LIKE ? COLLATE NOCASE OR CAST(playerid AS TEXT) LIKE ? OR next_ps LIKE ? COLLATE NOCASE OR playstyles_text LIKE ? OR roles_text LIKE ?)")
            args.extend([like]*7)
        if groups: where.append('('+' OR '.join(groups)+')')
    return ' AND '.join(where), args


def forget_storage(storage_keys) -> int:
    """v1.0.3: drop the cached overlay rows of deleted careers."""
    keys = sorted({str(k) for k in storage_keys if str(k or '')})
    if not keys: return 0
    with _connect() as con:
        n = 0
        for table in ('career_cache', 'players'):
            try: n += con.execute(f"DELETE FROM {table} WHERE storage_key IN ({','.join('?' * len(keys))})", keys).rowcount
            except sqlite3.OperationalError: pass     # cache never built
        con.commit()
    return n


def query_players(filters: dict[str, Any], sort_column: int = 0, ascending: bool = True, limit: int = 50, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    where, args = _filters_sql(filters)
    order = SORT_COLUMNS.get(int(sort_column), SORT_COLUMNS[0]) + (' ASC' if ascending else ' DESC')
    with _connect() as con:
        total = int(con.execute(f'SELECT COUNT(*) FROM players WHERE {where}', args).fetchone()[0])
        rs = con.execute(f'SELECT json_blob FROM players WHERE {where} ORDER BY {order}, playerid ASC LIMIT ? OFFSET ?', args + [int(limit), int(offset)]).fetchall()
    rows = []
    for r in rs:
        try: rows.append(json.loads(r['json_blob']))
        except Exception: pass
    return rows, total


def get_player(storage_key: str, playerid: int) -> dict[str, Any] | None:
    with _connect() as con:
        r = con.execute('SELECT json_blob FROM players WHERE storage_key=? AND playerid=?', (storage_key, int(playerid))).fetchone()
    if not r: return None
    try: return json.loads(r['json_blob'])
    except Exception: return None


def summary(storage_key: str, filters: dict[str, Any] | None = None) -> dict[str, int]:
    if not storage_key: return {}
    active = dict(filters or {})
    active['storage_key'] = storage_key
    where, args = _filters_sql(active)
    with _connect() as con:
        r = con.execute(f'''SELECT COUNT(*) AS players,
            SUM(CASE WHEN lifecycle='CLUB' AND json_extract(json_blob,'$.observed_this_checkpoint')=1 AND next_ps<>'' AND next_ps_pct>0 THEN 1 ELSE 0 END) AS developing,
            SUM(CASE WHEN lifecycle='CLUB' AND json_extract(json_blob,'$.observed_this_checkpoint')=1 AND next_plus<>'' AND next_plus_pct>0 THEN 1 ELSE 0 END) AS developing_plus,
            SUM(CASE WHEN lifecycle='CLUB' AND json_extract(json_blob,'$.observed_this_checkpoint')=1 AND role_progress_pct>0 THEN 1 ELSE 0 END) AS developing_role,
            SUM(CASE WHEN plus_eligible=1 AND plus_count=0 THEN 1 ELSE 0 END) AS plus_eligible,
            SUM(CASE WHEN normal_count>=cap THEN 1 ELSE 0 END) AS at_cap
            FROM players WHERE {where}''', args).fetchone()
    return {k:int(r[k] or 0) for k in ('players','developing','developing_plus','developing_role','plus_eligible','at_cap')} if r else {}


def diagnostics(storage_key: str) -> dict[str, Any]:
    from fc27_academy.paths import LOG_ROOT, BRIDGE_ROOT
    out: dict[str, Any] = {'cache': career_meta(storage_key) if storage_key else {}}
    act = BRIDGE_ROOT / 'bridge_activity.json'
    try: out['activity'] = json.loads(act.read_text(encoding='utf-8'))
    except Exception: out['activity'] = {}
    log = LOG_ROOT / 'bridge.log'
    lines: list[str] = []
    try:
        with log.open('rb') as f:
            f.seek(0, 2); size=f.tell(); f.seek(max(0,size-350000)); txt=f.read().decode('utf-8','replace')
        lines=txt.splitlines()
    except Exception: pass
    needles={
        'last_checkpoint':'FC27AE_BRIDGE_RX',
        'last_receipt':'FC27AE_SYNC_RECEIPT_RX',
        'last_bundle':'FC27AE_EVOLUTION_BUNDLE',
        'last_metadata':'FC27AE_METADATA',
        'last_lifecycle':'FC27AE_LIFECYCLE',
    }
    for key,needle in needles.items():
        for line in reversed(lines):
            if needle in line:
                out[key]=line.strip(); break
    return out
