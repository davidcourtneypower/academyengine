from __future__ import annotations
from fc27_academy.fsutil import replace_retry

"""Transactional runtime/checkpoint store for the v1.24 architecture.

FC27 remains authoritative for game data.  This database is authoritative for
Academy Engine runtime generations, save-aligned Academy checkpoints and the
small lifecycle state machine exposed to the external overlay.
"""

import datetime as _dt
import gzip
import hashlib
import json
import sqlite3
import time
from typing import Any

from fc27_academy.paths import ENGINE_DATA_ROOT, ACADEMY_STATE_ROOT, EVENTS_ROOT

DB_PATH = ENGINE_DATA_ROOT / "academy_engine.sqlite3"


def _date_ordinal(d: dict | None) -> int | None:
    if not isinstance(d, dict):
        return None
    try:
        return _dt.date(int(d["year"]), int(d["month"]), int(d["day"])).toordinal()
    except Exception:
        return None


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _pack(obj: Any) -> bytes:
    return gzip.compress(_json(obj).encode("utf-8"), compresslevel=6)


def _unpack(blob: bytes | None, default: Any) -> Any:
    if not blob:
        return default
    try:
        return json.loads(gzip.decompress(blob).decode("utf-8"))
    except Exception:
        return default


_SCHEMA_READY: set[str] = set()

# Retained history limits (v1.24.10). The snapshot journal is only a fallback for
# exact-save matching; save anchors are the primary record of real saves/loads.
SNAPSHOT_RETAIN_PER_CAREER = 120
ANCHOR_RETAIN_PER_CAREER = 96


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA foreign_keys=ON")
    # v1.24.10: schema/WAL setup and the lifecycle seed row run once per process.
    # Previously every lifecycle() read executed the whole script plus an INSERT
    # and COMMIT, i.e. a write transaction per read from several processes.
    key = str(DB_PATH)
    if key in _SCHEMA_READY and DB_PATH.exists():
        return con
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS lifecycle (
            id INTEGER PRIMARY KEY CHECK(id=1),
            state TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            runtime_session TEXT NOT NULL DEFAULT '',
            career_uid TEXT NOT NULL DEFAULT '',
            storage_key TEXT NOT NULL DEFAULT '',
            branch_id TEXT NOT NULL DEFAULT '',
            request_id TEXT NOT NULL DEFAULT '',
            date_json TEXT NOT NULL DEFAULT '{}',
            snapshot_sequence INTEGER NOT NULL DEFAULT 0,
            generation INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL
        );
        INSERT OR IGNORE INTO lifecycle(id,state,updated_at) VALUES(1,'NO_GAME',0);

        CREATE TABLE IF NOT EXISTS game_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            runtime_session TEXT NOT NULL,
            career_uid TEXT NOT NULL,
            storage_key TEXT NOT NULL,
            branch_id TEXT NOT NULL DEFAULT '',
            request_id TEXT NOT NULL,
            snapshot_sequence INTEGER NOT NULL DEFAULT 0,
            date_ordinal INTEGER,
            date_json TEXT NOT NULL DEFAULT '{}',
            trigger TEXT NOT NULL DEFAULT '',
            fingerprint TEXT NOT NULL,
            payload BLOB NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(runtime_session, request_id)
        );
        CREATE INDEX IF NOT EXISTS idx_game_snapshots_career_date
            ON game_snapshots(career_uid,date_ordinal,created_at);

        CREATE TABLE IF NOT EXISTS academy_checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            career_uid TEXT NOT NULL DEFAULT '',
            storage_key TEXT NOT NULL,
            branch_id TEXT NOT NULL DEFAULT '',
            date_ordinal INTEGER NOT NULL,
            date_json TEXT NOT NULL,
            trigger TEXT NOT NULL DEFAULT '',
            request_id TEXT NOT NULL DEFAULT '',
            is_anchor INTEGER NOT NULL DEFAULT 0,
            world_blob BLOB NOT NULL,
            events_blob BLOB NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_academy_checkpoints_date
            ON academy_checkpoints(storage_key,date_ordinal,is_anchor,created_at);

        CREATE TABLE IF NOT EXISTS read_generations (
            generation INTEGER PRIMARY KEY AUTOINCREMENT,
            runtime_session TEXT NOT NULL DEFAULT '',
            career_uid TEXT NOT NULL DEFAULT '',
            storage_key TEXT NOT NULL DEFAULT '',
            request_id TEXT NOT NULL DEFAULT '',
            date_json TEXT NOT NULL DEFAULT '{}',
            payload_hash TEXT NOT NULL,
            payload_text TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_read_generations_storage
            ON read_generations(storage_key,generation DESC);

        CREATE TABLE IF NOT EXISTS save_anchors (
            career_uid TEXT NOT NULL,
            game_fingerprint TEXT NOT NULL,
            storage_key TEXT NOT NULL DEFAULT '',
            branch_id TEXT NOT NULL DEFAULT '',
            date_ordinal INTEGER,
            date_json TEXT NOT NULL DEFAULT '{}',
            trigger TEXT NOT NULL DEFAULT '',
            world_blob BLOB NOT NULL,
            events_blob BLOB NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY(career_uid, game_fingerprint)
        );
        CREATE INDEX IF NOT EXISTS idx_save_anchors_date
            ON save_anchors(career_uid,date_ordinal,updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_game_snapshots_created
            ON game_snapshots(career_uid,created_at);
        """
    )
    con.commit()
    _SCHEMA_READY.add(key)
    return con


def lifecycle() -> dict[str, Any]:
    with _connect() as con:
        r = con.execute("SELECT * FROM lifecycle WHERE id=1").fetchone()
    d = dict(r) if r else {"state": "NO_GAME"}
    try:
        d["career_date"] = json.loads(d.pop("date_json", "{}") or "{}")
    except Exception:
        d["career_date"] = {}
    return d


def set_lifecycle(
    state: str,
    *,
    detail: str = "",
    runtime_session: str | None = None,
    career_uid: str | None = None,
    storage_key: str | None = None,
    branch_id: str | None = None,
    request_id: str | None = None,
    career_date: dict | None = None,
    snapshot_sequence: int | None = None,
    generation: int | None = None,
) -> dict[str, Any]:
    current = lifecycle()
    values = {
        "state": str(state or "NO_GAME").upper(),
        "detail": str(detail or ""),
        "runtime_session": current.get("runtime_session", "") if runtime_session is None else str(runtime_session or ""),
        "career_uid": current.get("career_uid", "") if career_uid is None else str(career_uid or ""),
        "storage_key": current.get("storage_key", "") if storage_key is None else str(storage_key or ""),
        "branch_id": current.get("branch_id", "") if branch_id is None else str(branch_id or ""),
        "request_id": current.get("request_id", "") if request_id is None else str(request_id or ""),
        "date_json": _json(current.get("career_date", {}) if career_date is None else (career_date or {})),
        "snapshot_sequence": int(current.get("snapshot_sequence") or 0) if snapshot_sequence is None else int(snapshot_sequence or 0),
        "generation": int(current.get("generation") or 0) if generation is None else int(generation or 0),
        "updated_at": time.time(),
    }
    with _connect() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """UPDATE lifecycle SET state=:state,detail=:detail,runtime_session=:runtime_session,
            career_uid=:career_uid,storage_key=:storage_key,branch_id=:branch_id,request_id=:request_id,
            date_json=:date_json,snapshot_sequence=:snapshot_sequence,generation=:generation,updated_at=:updated_at
            WHERE id=1""",
            values,
        )
        con.commit()
    return lifecycle()


def purge_career(career_uid: str, storage_keys: list[str]) -> dict[str, int]:
    """v1.0.3: remove every stored checkpoint, save anchor, game snapshot and read generation
    of one career (all its branches), so deleted engine data cannot be restored later."""
    uid = str(career_uid or ""); keys = sorted({str(k) for k in storage_keys if str(k or "")})
    out = {}
    with _connect() as con:
        for table in ("academy_checkpoints", "save_anchors", "game_snapshots", "read_generations"):
            where, args = [], []
            if uid:
                where.append("career_uid=?"); args.append(uid)
            if keys:
                where.append(f"storage_key IN ({','.join('?' * len(keys))})"); args.extend(keys)
            if not where:
                out[table] = 0; continue
            out[table] = con.execute(f"DELETE FROM {table} WHERE " + " OR ".join(where), args).rowcount
        con.commit()
    return out


def detach(detail: str = "Career Mode is not active") -> dict[str, Any]:
    # A detach invalidates only the active runtime/read generation. Persistent
    # career/checkpoint rows are intentionally retained.
    return set_lifecycle(
        "DETACHED",
        detail=detail,
        runtime_session="",
        career_uid="",
        storage_key="",
        branch_id="",
        request_id="",
        career_date={},
        snapshot_sequence=0,
        generation=0,
    )



def _safe_storage(v: str) -> str:
    return ''.join(c for c in str(v or '') if c.isalnum() or c in '-_') or 'UNKNOWN_SAVE'


def stable_game_fingerprint(payload: dict) -> str:
    """Fingerprint FC27-owned save state, excluding Academy/runtime transport fields."""
    career = payload.get('career') or {}
    canonical_players = []
    fields = (
        'playerid','clubteamid','leagueid','preferredposition1','positions','overallrating',
        'potential','nationality','birthdate','firstnameid','lastnameid','commonnameid',
        'playerjerseynameid','trait1','trait2','icontrait1','icontrait2',
        'role1','role2','role3','role4','role5','roles','attributes',
    )
    for player in payload.get('players') or []:
        if not isinstance(player, dict):
            continue
        canonical_players.append({k: player.get(k) for k in fields if k in player})
    canonical_players.sort(key=lambda row: int(row.get('playerid') or 0))
    base = {
        'career_uid': str(payload.get('save_uid') or payload.get('career_uid') or ''),
        'date': career.get('date') or {},
        'user_teamid': career.get('user_teamid'),
        'players': canonical_players,
    }
    return hashlib.sha256(_json(base).encode('utf-8')).hexdigest()


def _read_events(storage_key: str) -> dict:
    ep = EVENTS_ROOT / _safe_storage(storage_key) / 'events.json'
    try:
        return json.loads(ep.read_text(encoding='utf-8'))
    except Exception:
        return {'schema': 1, 'events': []}


def upsert_save_anchor(*, payload: dict, storage_key: str, branch_id: str = '', trigger: str = '') -> dict[str, Any]:
    """Persist Academy state corresponding to one actually loaded/saved FC27 state."""
    wp = ACADEMY_STATE_ROOT / 'saves' / _safe_storage(storage_key) / 'generated_world.json'
    if not wp.exists():
        return {'status': 'SKIP', 'reason': 'WORLD_MISSING'}
    try:
        world = json.loads(wp.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'status': 'ERROR', 'reason': f'WORLD_READ:{exc}'}
    events = _read_events(storage_key)
    career_uid = str(payload.get('save_uid') or payload.get('career_uid') or world.get('career_uid') or '')
    fp = stable_game_fingerprint(payload)
    date = (payload.get('career') or {}).get('date') or (world.get('career') or {}).get('date') or {}
    ordv = _date_ordinal(date)
    with _connect() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute(
            '''INSERT INTO save_anchors(career_uid,game_fingerprint,storage_key,branch_id,date_ordinal,date_json,trigger,world_blob,events_blob,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(career_uid,game_fingerprint) DO UPDATE SET
                 storage_key=excluded.storage_key,branch_id=excluded.branch_id,date_ordinal=excluded.date_ordinal,
                 date_json=excluded.date_json,trigger=excluded.trigger,world_blob=excluded.world_blob,
                 events_blob=excluded.events_blob,updated_at=excluded.updated_at''',
            (career_uid, fp, str(storage_key), str(branch_id or ''), ordv, _json(date), str(trigger or ''), _pack(world), _pack(events), time.time()),
        )
        # Bounded retention: keep the newest anchors per career; PREPARE_FOR_SAVE
        # anchors (real saves) are preferred over load-only anchors when trimming.
        con.execute(
            """DELETE FROM save_anchors WHERE career_uid=? AND game_fingerprint IN (
                 SELECT game_fingerprint FROM save_anchors WHERE career_uid=?
                 ORDER BY (trigger='PREPARE_FOR_SAVE') DESC, updated_at DESC LIMIT -1 OFFSET ?)""",
            (career_uid, career_uid, ANCHOR_RETAIN_PER_CAREER),
        )
        con.commit()
    return {'status': 'ANCHORED', 'fingerprint': fp, 'date_ordinal': ordv}


def find_exact_save_anchor(payload: dict, anchors_only: bool = False) -> dict[str, Any]:
    """Locate an exact previously observed FC27 save without mutating state.

    anchors_only restricts matching to real save/load anchors. Boundary re-syncs use
    it: matching any journalled mid-play snapshot is not evidence of a reload.
    """
    career_uid=str(payload.get('save_uid') or payload.get('career_uid') or '')
    if not career_uid: return {'status':'MISS','reason':'IDENTITY_MISSING'}
    fp=stable_game_fingerprint(payload)
    with _connect() as con:
        r=con.execute('SELECT storage_key,branch_id,date_ordinal,updated_at,world_blob FROM save_anchors WHERE career_uid=? AND game_fingerprint=? LIMIT 1',(career_uid,fp)).fetchone()
        if r:
            d=dict(r); blob=d.pop('world_blob',None)
            if _verified_world(blob,payload,fp):
                d.update({'status':'FOUND','fingerprint':fp,'source':'SAVE_ANCHOR'}); return d
            d.update({'status':'REJECTED_STATE_MISMATCH','fingerprint':fp,'source':'SAVE_ANCHOR'}); return d
        if anchors_only:
            return {'status':'MISS','fingerprint':fp,'reason':'ANCHORS_ONLY'}
        target_ord=_date_ordinal((payload.get('career') or {}).get('date') or {})
        snaps=con.execute('SELECT * FROM game_snapshots WHERE career_uid=? AND (? IS NULL OR date_ordinal=?) ORDER BY created_at ASC',(career_uid,target_ord,target_ord)).fetchall()
        for sr in snaps:
            prior=_unpack(sr['payload'],{})
            if prior and stable_game_fingerprint(prior)==fp:
                cp=con.execute('SELECT storage_key,branch_id,date_ordinal,created_at,world_blob FROM academy_checkpoints WHERE career_uid=? AND request_id=? ORDER BY created_at ASC LIMIT 1',(career_uid,str(sr['request_id'] or ''))).fetchone()
                if cp is None:
                    cp=con.execute('SELECT storage_key,branch_id,date_ordinal,created_at,world_blob FROM academy_checkpoints WHERE career_uid=? AND created_at>=? AND created_at<=? ORDER BY created_at ASC LIMIT 1',(career_uid,float(sr['created_at']),float(sr['created_at'])+30.0)).fetchone()
                if cp:
                    d=dict(cp); blob=d.pop('world_blob',None)
                    if _verified_world(blob,payload,fp):
                        d.update({'status':'FOUND','fingerprint':fp,'source':'TRANSACTION_JOURNAL'}); return d
    return {'status':'MISS','fingerprint':fp}


def _world_game_fingerprint(world: dict, payload: dict) -> str:
    """Fingerprint the FC27 state a stored Academy world was reconciled against."""
    players = [dict((p or {}).get('game') or {}) for p in (world.get('players') or {}).values()
               if (p or {}).get('observed_this_checkpoint', True)]
    career = dict(payload.get('career') or {})
    career['date'] = (world.get('career') or {}).get('date') or {}
    if (world.get('career') or {}).get('user_teamid') is not None:
        career['user_teamid'] = (world.get('career') or {}).get('user_teamid')
    return stable_game_fingerprint({'save_uid': payload.get('save_uid') or payload.get('career_uid'),
                                    'career': career, 'players': players})


def _verified_world(blob, payload: dict, fp: str) -> bool:
    try:
        return _world_game_fingerprint(_unpack(blob, {}), payload) == fp
    except Exception:
        return False


def restore_exact_save_anchor(*, payload: dict, storage_key: str, branch_id: str = '', anchors_only: bool = False) -> dict[str, Any]:
    """Restore Academy state for the exact FC27 save currently being loaded.

    v1.24.10 verifies that the stored world really was reconciled against this
    exact FC27 state before replacing anything; a mismatch is rejected and logged
    instead of silently swapping in an unrelated world.
    """
    career_uid = str(payload.get('save_uid') or payload.get('career_uid') or '')
    if not career_uid or not storage_key:
        return {'status': 'MISS', 'reason': 'IDENTITY_MISSING'}
    fp = stable_game_fingerprint(payload)
    with _connect() as con:
        r = con.execute('SELECT * FROM save_anchors WHERE career_uid=? AND game_fingerprint=? LIMIT 1', (career_uid, fp)).fetchone()
    if not r and anchors_only:
        return {'status': 'MISS', 'fingerprint': fp, 'reason': 'ANCHORS_ONLY'}
    if not r:
        # Native v1.24 journal recovery: before save_anchors existed, every full
        # FC27 snapshot and Academy checkpoint was already transactionally stored.
        # If this exact game state was seen before, recover the Academy checkpoint
        # created for that request rather than treating unsaved later progress as
        # belonging to the reloaded save. This is normal current-store recovery,
        # not legacy/import compatibility.
        target_ord=_date_ordinal((payload.get('career') or {}).get('date') or {})
        with _connect() as con:
            snaps=con.execute(
                'SELECT * FROM game_snapshots WHERE career_uid=? AND (? IS NULL OR date_ordinal=?) ORDER BY created_at ASC',
                (career_uid,target_ord,target_ord),
            ).fetchall()
            matched=None
            for sr in snaps:
                prior=_unpack(sr['payload'],{})
                if prior and stable_game_fingerprint(prior)==fp:
                    matched=sr; break
            cp=None
            if matched is not None:
                # Prefer the checkpoint from the same bridge request; otherwise use
                # the first checkpoint created immediately after that snapshot.
                cp=con.execute(
                    'SELECT * FROM academy_checkpoints WHERE career_uid=? AND request_id=? ORDER BY created_at ASC LIMIT 1',
                    (career_uid,str(matched['request_id'] or '')),
                ).fetchone()
                if cp is None:
                    cp=con.execute(
                        'SELECT * FROM academy_checkpoints WHERE career_uid=? AND created_at>=? AND created_at<=? ORDER BY created_at ASC LIMIT 1',
                        (career_uid,float(matched['created_at']),float(matched['created_at'])+30.0),
                    ).fetchone()
        if cp is None:
            return {'status': 'MISS', 'fingerprint': fp}
        d=dict(cp)
        d['world_blob']=d.get('world_blob'); d['events_blob']=d.get('events_blob')
        d['storage_key']=str(d.get('storage_key') or storage_key)
        d['branch_id']=str(d.get('branch_id') or branch_id)
    else:
        d = dict(r)
    world = _unpack(d.get('world_blob'), {})
    events = _unpack(d.get('events_blob'), {'schema': 1, 'events': []})
    try:
        stored_fp = _world_game_fingerprint(world, payload)
    except Exception:
        stored_fp = ''
    if stored_fp != fp:
        return {'status': 'REJECTED_STATE_MISMATCH', 'fingerprint': fp, 'stored_world_fingerprint': stored_fp,
                'anchor_storage_key': str(d.get('storage_key') or ''), 'date_ordinal': d.get('date_ordinal')}
    world['save_uid'] = str(storage_key)
    world['storage_key'] = str(storage_key)
    world['career_uid'] = career_uid
    world['branch_id'] = str(branch_id or world.get('branch_id') or '')
    world['runtime_session'] = '__RESTORED_SAVE_ANCHOR__'
    world['runtime_day_epoch'] = 0
    wp = ACADEMY_STATE_ROOT / 'saves' / _safe_storage(storage_key) / 'generated_world.json'
    ep = EVENTS_ROOT / _safe_storage(storage_key) / 'events.json'
    wp.parent.mkdir(parents=True, exist_ok=True); ep.parent.mkdir(parents=True, exist_ok=True)
    wtmp = wp.with_suffix(wp.suffix + '.tmp'); etmp = ep.with_suffix(ep.suffix + '.tmp')
    wtmp.write_text(json.dumps(world, ensure_ascii=False, separators=(',', ':'), sort_keys=True), encoding='utf-8')
    etmp.write_text(json.dumps(events, ensure_ascii=False, separators=(',', ':'), sort_keys=True), encoding='utf-8')
    replace_retry(wtmp,wp); replace_retry(etmp,ep)
    return {
        'status': 'RESTORED', 'fingerprint': fp,
        'anchor_storage_key': str(d.get('storage_key') or ''),
        'anchor_branch_id': str(d.get('branch_id') or ''),
        'date_ordinal': d.get('date_ordinal'),
    }


def record_game_snapshot(
    *,
    payload: dict,
    storage_key: str,
    branch_id: str = "",
) -> dict[str, Any]:
    runtime_session = str(payload.get("runtime_session") or "")
    career_uid = str(payload.get("save_uid") or payload.get("career_uid") or "")
    request_id = str(payload.get("request_id") or payload.get("checkpoint_id") or "")
    seq = int(payload.get("snapshot_sequence") or payload.get("day_epoch") or 0)
    career_date = (payload.get("career") or {}).get("date") or {}
    ordv = _date_ordinal(career_date)
    raw = _json(payload).encode("utf-8")
    fingerprint = hashlib.sha256(raw).hexdigest()
    now = time.time()
    packed = gzip.compress(raw, compresslevel=5)
    with _connect() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """INSERT OR IGNORE INTO game_snapshots(runtime_session,career_uid,storage_key,branch_id,
            request_id,snapshot_sequence,date_ordinal,date_json,trigger,fingerprint,payload,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                runtime_session, career_uid, str(storage_key or ""), str(branch_id or ""), request_id, seq,
                ordv, _json(career_date), str(payload.get("trigger") or ""), fingerprint, packed, now,
            ),
        )
        con.execute(
            """DELETE FROM game_snapshots WHERE career_uid=? AND id IN (
                 SELECT id FROM game_snapshots WHERE career_uid=? ORDER BY created_at DESC LIMIT -1 OFFSET ?)""",
            (career_uid, career_uid, SNAPSHOT_RETAIN_PER_CAREER),
        )
        con.commit()
    return {"fingerprint": fingerprint, "date_ordinal": ordv, "snapshot_sequence": seq}


def create_checkpoint(
    storage_key: str,
    *,
    world: dict,
    events: dict,
    trigger: str,
    request_id: str = "",
    career_uid: str = "",
    branch_id: str = "",
) -> dict[str, Any]:
    career_date = (world.get("career") or {}).get("date") or {}
    ordv = _date_ordinal(career_date)
    if ordv is None:
        return {"status": "SKIP", "reason": "DATE_MISSING"}
    anchor = str(trigger or "").upper() in {
        "PREPARE_FOR_SAVE", "SCREEN_LOADED_BASELINE", "CAREER_SETTLED_BASELINE", "SAVE_STABILIZED", "LOAD_RECONCILED"
    }
    with _connect() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """INSERT INTO academy_checkpoints(career_uid,storage_key,branch_id,date_ordinal,date_json,
            trigger,request_id,is_anchor,world_blob,events_blob,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(career_uid or world.get("career_uid") or ""), str(storage_key), str(branch_id or world.get("branch_id") or ""),
                ordv, _json(career_date), str(trigger or "CHECKPOINT"), str(request_id or ""), 1 if anchor else 0,
                _pack(world), _pack(events or {"schema": 1, "events": []}), time.time(),
            ),
        )
        # Bound storage while keeping enough history for season/save rollback.
        ids = [r[0] for r in con.execute(
            "SELECT id FROM academy_checkpoints WHERE storage_key=? ORDER BY created_at DESC LIMIT -1 OFFSET 80",
            (str(storage_key),),
        ).fetchall()]
        if ids:
            con.executemany("DELETE FROM academy_checkpoints WHERE id=?", [(i,) for i in ids])
        con.commit()
    return {"status": "OK", "date_ordinal": ordv, "anchor": anchor}


def checkpoint_for_date(storage_key: str, career_date: dict | None) -> dict[str, Any] | None:
    target = _date_ordinal(career_date)
    if not storage_key or target is None:
        return None
    with _connect() as con:
        r = con.execute(
            """SELECT * FROM academy_checkpoints WHERE storage_key=? AND date_ordinal<=?
            ORDER BY (date_ordinal=? ) DESC,date_ordinal DESC,is_anchor DESC,created_at DESC LIMIT 1""",
            (str(storage_key), target, target),
        ).fetchone()
    if not r:
        return None
    d = dict(r)
    d["world"] = _unpack(d.pop("world_blob"), {})
    d["events"] = _unpack(d.pop("events_blob"), {"schema": 1, "events": []})
    try:
        d["career_date"] = json.loads(d.pop("date_json") or "{}")
    except Exception:
        d["career_date"] = {}
    return d


def clear_events_in_checkpoints(storage_key: str) -> int:
    if not storage_key:
        return 0
    changed = 0
    with _connect() as con:
        rows = con.execute(
            "SELECT id,world_blob FROM academy_checkpoints WHERE storage_key=?", (str(storage_key),)
        ).fetchall()
        con.execute("BEGIN IMMEDIATE")
        for r in rows:
            world = _unpack(r["world_blob"], {})
            removable = {
                "PLAYSTYLE_PRODUCTION_COMMIT", "PLAYSTYLE_PLUS_PRODUCTION_COMMIT", "PLUS_PRODUCTION_COMMIT", "ROLE_PRODUCTION_COMMIT"
            }
            for player in (world.get("players") or {}).values():
                hist = player.get("history") or []
                player["history"] = [h for h in hist if not (isinstance(h, dict) and str(h.get("type") or "").upper() in removable)]
            con.execute(
                "UPDATE academy_checkpoints SET world_blob=?,events_blob=? WHERE id=?",
                (_pack(world), _pack({"schema": 1, "events": []}), int(r["id"])),
            )
            changed += 1
        con.commit()
    return changed


def publish_generation(
    payload_text: str,
    *,
    runtime_session: str,
    career_uid: str,
    storage_key: str,
    request_id: str,
    career_date: dict | None,
    promote: bool = True,
) -> int:
    h = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    with _connect() as con:
        latest = con.execute(
            "SELECT generation,payload_hash,runtime_session,career_uid,storage_key,request_id FROM read_generations ORDER BY generation DESC LIMIT 1"
        ).fetchone()
        if latest and str(latest['payload_hash'])==h and str(latest['runtime_session'])==str(runtime_session or '') and str(latest['career_uid'])==str(career_uid or '') and str(latest['storage_key'])==str(storage_key or '') and str(latest['request_id'])==str(request_id or ''):
            gen=int(latest['generation'])
            if promote:
                con.execute("UPDATE lifecycle SET generation=?,state='READY',updated_at=? WHERE id=1", (gen,time.time()))
            con.commit(); return gen
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            """INSERT INTO read_generations(runtime_session,career_uid,storage_key,request_id,date_json,payload_hash,payload_text,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (str(runtime_session or ""), str(career_uid or ""), str(storage_key or ""), str(request_id or ""), _json(career_date or {}), h, payload_text, time.time()),
        )
        gen = int(cur.lastrowid)
        if promote:
            con.execute("UPDATE lifecycle SET generation=?,state='READY',updated_at=? WHERE id=1", (gen, time.time()))
        # Keep recent generations for diagnostics/replay without growing forever.
        con.execute("DELETE FROM read_generations WHERE generation < ?", (max(0, gen - 120),))
        con.commit()
    return gen


def generation_storage_key(generation: int) -> str:
    """Storage key a published read generation belonged to ('' if unknown)."""
    try:
        g = int(generation)
    except (TypeError, ValueError):
        return ''
    if g <= 0:
        return ''
    with _connect() as con:
        r = con.execute("SELECT storage_key FROM read_generations WHERE generation=?", (g,)).fetchone()
    return str(r['storage_key'] or '') if r else ''


def latest_generation() -> dict[str, Any] | None:
    with _connect() as con:
        r = con.execute("SELECT * FROM read_generations ORDER BY generation DESC LIMIT 1").fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["career_date"] = json.loads(d.pop("date_json") or "{}")
    except Exception:
        d["career_date"] = {}
    return d


def diagnostics() -> dict[str, Any]:
    out = {"db": str(DB_PATH), "lifecycle": lifecycle()}
    with _connect() as con:
        out["snapshot_count"] = int(con.execute("SELECT COUNT(*) FROM game_snapshots").fetchone()[0])
        out["checkpoint_count"] = int(con.execute("SELECT COUNT(*) FROM academy_checkpoints").fetchone()[0])
        out["generation_count"] = int(con.execute("SELECT COUNT(*) FROM read_generations").fetchone()[0])
    return out
