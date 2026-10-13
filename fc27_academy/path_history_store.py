"""Immutable bounded development histories, shared by world/save references.

Histories are committed before a world may reference them. A crash can leave an
unreferenced blob, never a half-written referenced history. Old inline worlds
remain readable. Missing/corrupt referenced data raises, rather than silently
turning history into an empty list. The existing 12/48-entry limits are retained.
"""
from contextlib import closing, contextmanager
from copy import deepcopy
import gzip,hashlib,json,sqlite3,threading,time
from functools import wraps
from .paths import ENGINE_DATA_ROOT

DB_PATH=ENGINE_DATA_ROOT/'academy_engine.sqlite3'
_local=threading.local()

META_KEYS=('playstyle_progress_meta','playstyle_plus_progress_meta','role_progress_meta')

def _connect():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(DB_PATH,timeout=15)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=FULL')
    con.execute('CREATE TABLE IF NOT EXISTS development_histories (digest TEXT PRIMARY KEY, payload BLOB NOT NULL, created_at REAL NOT NULL DEFAULT 0)')
    if 'created_at' not in {row[1] for row in con.execute('PRAGMA table_info(development_histories)')}:
        con.execute('ALTER TABLE development_histories ADD COLUMN created_at REAL NOT NULL DEFAULT 0')
    con.commit();return con

@contextmanager
def connection():
    current=getattr(_local,'connection',None)
    if current is not None:
        yield current
    else:
        with closing(_connect()) as con:yield con

def batched_history(fn):
    @wraps(fn)
    def run(*args,**kwargs):
        if getattr(_local,'connection',None) is not None:return fn(*args,**kwargs)
        with closing(_connect()) as con:
            _local.connection=con
            try:return fn(*args,**kwargs)
            finally:_local.connection=None
    return run

def history(meta):
    if 'history' in meta:return meta['history']
    ref=meta.get('history_ref')
    if not ref:return []
    with connection() as con:
        row=con.execute('SELECT payload FROM development_histories WHERE digest=?',(ref,)).fetchone()
    if row is None:raise RuntimeError('Development history reference missing: '+str(ref))
    raw=gzip.decompress(row[0])
    if hashlib.sha256(raw).hexdigest()!=ref:raise RuntimeError('Development history integrity check failed')
    value=json.loads(raw)
    if not isinstance(value,list):raise RuntimeError('Invalid development history')
    return value

def editable_history(meta):
    if 'history' not in meta:meta['history']=history(meta)
    meta.pop('history_ref',None)
    return meta['history']

def externalize(world):
    pending={}; updates=[]
    for player in (world.get('players') or {}).values():
        for key in META_KEYS:
            for meta in ((player.get('engine') or {}).get(key) or {}).values():
                if 'history' not in meta:continue
                raw=json.dumps(meta['history'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
                ref=hashlib.sha256(raw).hexdigest()
                if ref not in pending:pending[ref]=(ref,gzip.compress(raw,compresslevel=1),time.time())
                updates.append((meta,ref))
    if pending:
        with connection() as con, con:
            con.executemany('INSERT OR IGNORE INTO development_histories(digest,payload,created_at) VALUES(?,?,?)',pending.values())
        for meta,ref in updates:
            meta.pop('history',None);meta['history_ref']=ref
    return world

def hydrate_world(world):
    """Compatibility/export/test helper; ordinary list reads do not call this."""
    out=deepcopy(world)
    for player in (out.get('players') or {}).values():
        for key in META_KEYS:
            for meta in ((player.get('engine') or {}).get(key) or {}).values():
                if 'history_ref' in meta:editable_history(meta)
    return out

def collect_unused(*,now=None):
    """Idle-only daily sweep. Preserve all worlds, checkpoints, anchors and UI rows.

    A one-day age grace also protects newly written, not-yet-published blobs.
    Any unreadable root aborts the sweep; uncertainty must never erase history.
    Freed SQLite pages are reused without a blocking VACUUM.
    """
    from .paths import ACADEMY_STATE_ROOT,CACHE_ROOT
    now=time.time() if now is None else now
    def references(obj):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key=='history_ref' and isinstance(value,str):yield value
                else:yield from references(value)
        elif isinstance(obj,list):
            for value in obj:yield from references(value)
    with connection() as con, con:
        con.execute('CREATE TABLE IF NOT EXISTS history_maintenance (id INTEGER PRIMARY KEY, last_gc REAL NOT NULL)')
        last=con.execute('SELECT last_gc FROM history_maintenance WHERE id=1').fetchone()
        if last and now-last[0]<86400:return {'status':'NOT_DUE','removed':0}
        con.execute('BEGIN IMMEDIATE')
        if not con.execute('SELECT 1 FROM development_histories WHERE created_at<? LIMIT 1',(now-86400,)).fetchone():
            con.execute('INSERT OR REPLACE INTO history_maintenance VALUES(1,?)',(now,))
            return {'status':'NO_OLD_BLOBS','removed':0}
        keep=set()
        for path in (ACADEMY_STATE_ROOT/'saves').glob('*/generated_world.json'):
            keep.update(references(json.loads(path.read_text(encoding='utf-8'))))
        tables={row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('academy_checkpoints','save_anchors'):
            if table in tables:
                for row in con.execute('SELECT world_blob FROM '+table):
                    keep.update(references(json.loads(gzip.decompress(row[0]))))
        cache=CACHE_ROOT/'academy_read_model.sqlite3'
        if cache.exists():
            with closing(sqlite3.connect(cache,timeout=10)) as rc:
                if rc.execute("SELECT 1 FROM sqlite_master WHERE name='players'").fetchone():
                    for row in rc.execute('SELECT json_blob FROM players'):
                        keep.update(references(json.loads(row[0])))
        con.execute('CREATE TEMP TABLE keep_history (digest TEXT PRIMARY KEY)')
        con.executemany('INSERT OR IGNORE INTO keep_history VALUES(?)',[(ref,) for ref in keep])
        removed=con.execute('DELETE FROM development_histories WHERE created_at<? AND NOT EXISTS (SELECT 1 FROM keep_history k WHERE k.digest=development_histories.digest)',(now-86400,)).rowcount
        con.execute('INSERT OR REPLACE INTO history_maintenance VALUES(1,?)',(now,))
        return {'status':'COMPLETE','removed':removed}
