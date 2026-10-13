"""Regen-face library and per-player face assignment (v1.24.31).

The user points the Academy Engine at a local folder of face images:

    <library>\\<Region>\\*.png         men's faces, one folder per region
    <library>\\WF\\<Region>\\*.png     women's faces

Nothing here ships, copies or modifies those images. Assignment only stores the
chosen file (relative to the library) in ``player['engine']['face']`` so the choice
travels with the career's world file:

    {"file": "Ireland/PP16Ireland0001.png", "region": "Ireland", "gender": "M",
     "source": "auto" | "user", "identity": "<pid>|<birthdate>|<nationality>|<gender>"}

Choices are deterministic per career and player identity, avoid repeats inside a
career while the library has unused faces, and are redone when FC27 reuses a player
ID for a different person. A face the user picked is kept until the identity changes.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import random
import threading
from pathlib import Path

from . import face_regions as FR
from .nationalities import nationality_name
from .paths import USER_ROOT

IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.dds'}
WOMEN_DIR = 'wf'
SETTINGS_DEFAULTS = {'face_enabled': False, 'face_library_path': '', 'face_write_ingame': False}
INDEX_CACHE_NAME = 'face_index.json'
INDEX_SCHEMA = 2

_lock = threading.Lock()
_mem: dict[str, tuple[tuple, dict]] = {}


def _norm(name: str) -> str:
    return ''.join(c for c in str(name).lower() if c.isalnum())


# v1.24.37: the face feature is hidden from the launcher and overlay for now. While hidden it is
# also treated as off everywhere (nothing assigned, shown or written to FC27); faces already saved
# with careers are kept, so showing it again restores them. Developers/tests can show it with
# the environment variable FC27AE_SHOW_FACES=1.
FACES_FEATURE_VISIBLE = False


def faces_visible() -> bool:
    return FACES_FEATURE_VISIBLE or os.environ.get('FC27AE_SHOW_FACES') == '1'


def face_settings() -> dict:
    """Global face settings from manager_settings.json (shared with the launcher)."""
    out = dict(SETTINGS_DEFAULTS)
    if not faces_visible():
        return out                      # hidden: off (defaults), whatever was saved
    try:
        raw = json.loads((USER_ROOT / 'manager_settings.json').read_text(encoding='utf-8'))
        for k in SETTINGS_DEFAULTS:
            if k in raw:
                out[k] = raw[k]
    except Exception:
        pass
    out['face_enabled'] = bool(out.get('face_enabled'))
    out['face_write_ingame'] = bool(out.get('face_write_ingame'))
    out['face_library_path'] = str(out.get('face_library_path') or '').strip()
    return out


def gender_code(value) -> str:
    """FC27 players.gender: 0 = male, 1 = female. Unknown is treated as male."""
    try:
        return 'F' if int(value) == 1 else 'M'
    except (TypeError, ValueError):
        return 'M'


def gender_label(value) -> str:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return 'Unknown'
    return 'Female' if v == 1 else 'Male' if v == 0 else 'Unknown'


# ---------------------------------------------------------------------------
# Library index
# ---------------------------------------------------------------------------

def _region_dirs(root: Path) -> list[tuple[str, str, Path]]:
    """(gender, region name, path) for every region folder in the library."""
    out = []
    try:
        top = sorted((e for e in os.scandir(root) if e.is_dir()), key=lambda e: e.name.lower())
    except OSError:
        return out
    for e in top:
        if _norm(e.name) == WOMEN_DIR:
            try:
                sub = sorted((s for s in os.scandir(e.path) if s.is_dir()), key=lambda s: s.name.lower())
            except OSError:
                sub = []
            for s in sub:
                out.append(('F', s.name, Path(s.path)))
        else:
            out.append(('M', e.name, Path(e.path)))
    return out


def _signature(root: Path, dirs) -> tuple:
    sig = []
    for p in [root] + [d for _, _, d in dirs]:
        try:
            sig.append((str(p), int(p.stat().st_mtime_ns)))
        except OSError:
            sig.append((str(p), 0))
    return tuple(sig)


def _scan_region(path: Path, root: Path) -> list[str]:
    files = []
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for fn in sorted(filenames):
            if os.path.splitext(fn)[1].lower() in IMAGE_EXT:
                files.append(Path(dirpath, fn).relative_to(root).as_posix())
    return files


def load_library(root, *, use_disk_cache: bool = True) -> dict:
    """Index of the face library: {'root', 'M': {region: [rel files]}, 'F': {...}}.

    Cached in memory and in ``face_index.json`` keyed by folder modification times,
    so adding or removing faces in a region folder is picked up on the next checkpoint.
    """
    root = Path(str(root or '')).expanduser()
    empty = {'root': str(root), 'M': {}, 'F': {}, 'count': 0}
    if not str(root).strip() or not root.is_dir():
        return empty
    dirs = _region_dirs(root)
    sig = _signature(root, dirs)
    key = str(root.resolve())
    with _lock:
        hit = _mem.get(key)
        if hit and hit[0] == sig:
            return hit[1]
    cache_path = USER_ROOT / INDEX_CACHE_NAME
    if use_disk_cache:
        try:
            disk = json.loads(cache_path.read_text(encoding='utf-8'))
            if disk.get('schema') == INDEX_SCHEMA and disk.get('root') == key and [tuple(x) for x in disk.get('signature', [])] == [tuple(x) for x in sig]:
                idx = disk['index']
                with _lock:
                    _mem[key] = (sig, idx)
                return idx
        except Exception:
            pass
    idx = {'root': str(root), 'M': {}, 'F': {}, 'count': 0}
    for g, name, path in dirs:
        files = _scan_region(path, root)
        if files:
            idx[g].setdefault(name, []).extend(files)
            idx['count'] += len(files)
    with _lock:
        _mem[key] = (sig, idx)
    if use_disk_cache:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'schema': INDEX_SCHEMA, 'root': key, 'signature': [list(x) for x in sig], 'index': idx}), encoding='utf-8')
            os.replace(tmp, cache_path)
        except Exception:
            pass
    return idx


def library_summary(idx: dict) -> str:
    m = sum(len(v) for v in idx.get('M', {}).values())
    f = sum(len(v) for v in idx.get('F', {}).values())
    return f"{m:,} men's faces in {len(idx.get('M', {}))} regions, {f:,} women's faces in {len(idx.get('F', {}))} regions"


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

def _user_overrides() -> dict:
    try:
        raw = json.loads((USER_ROOT / 'face_regions.json').read_text(encoding='utf-8'))
        return {str(k): [(str(r), float(w)) for r, w in v] for k, v in raw.items()}
    except Exception:
        return {}


def _available_map(regions: dict) -> dict[str, str]:
    """normalised region name -> actual folder name present for this gender."""
    return {_norm(name): name for name in regions}


def _resolve(region: str, avail: dict[str, str]) -> str | None:
    for cand in FR.FALLBACKS.get(region, [region]):
        hit = avail.get(_norm(cand))
        if hit:
            return hit
    return avail.get(_norm(region))


_FAM_BY_NORM = {_norm(r): f for r, f in FR.FAMILY_OF.items()}


@functools.lru_cache(maxsize=4096)
def _families_of(folder: str) -> frozenset:
    n = _norm(folder)
    out = {_FAM_BY_NORM[n]} if n in _FAM_BY_NORM else set()
    out |= {f for f, names in FR.FAMILY_FOLDERS.items() if n in names}
    return frozenset(out)


def _family_pool(fam: str, avail: dict[str, str]) -> list[str]:
    return sorted(name for name in avail.values() if fam in _families_of(name))


def _resolve_shares(region: str, avail: dict[str, str]) -> list[tuple[str, float]]:
    """Folder(s) standing in for ``region``: its fallback chain, else its family, else a near family."""
    hit = _resolve(region, avail)
    if hit:
        return [(hit, 1.0)]
    fam = FR.FAMILY_OF.get(region)
    for f in ([fam] + FR.FAMILY_NEAR.get(fam, [])) if fam else []:
        pool = _family_pool(f, avail)
        if pool:
            return [(name, 1.0 / len(pool)) for name in pool]
    return []


_WEIGHTS_MEMO: dict = {}


def region_weights(nationality, gender: str, idx: dict, overrides: dict | None = None) -> list[tuple[str, float]]:
    """Weighted list of available region folders for a nationality and gender (memoised per library)."""
    key = (str(nationality), gender, idx.get('root'), idx.get('count'), tuple(sorted(idx.get(gender, {}))),
           json.dumps(overrides or {}, sort_keys=True))
    hit = _WEIGHTS_MEMO.get(key)
    if hit is None:
        if len(_WEIGHTS_MEMO) > 4096:
            _WEIGHTS_MEMO.clear()
        hit = _WEIGHTS_MEMO[key] = _region_weights(nationality, gender, idx, overrides)
    return list(hit)


def _region_weights(nationality, gender: str, idx: dict, overrides: dict | None = None) -> list[tuple[str, float]]:
    regions = idx.get(gender, {})
    if not regions:
        return []
    avail = _available_map(regions)
    name = nationality_name(nationality)
    table = (overrides or {}).get(name) or FR.NATION_WEIGHTS.get(name) or FR.DEFAULT_WEIGHTS
    acc: dict[str, float] = {}
    for tbl in (table, FR.DEFAULT_WEIGHTS):
        for region, w in tbl:
            if w <= 0:
                continue
            for hit, share in _resolve_shares(region, avail):
                acc[hit] = acc.get(hit, 0.0) + float(w) * share
        if acc:
            break
    if not acc:  # folders with unrecognised names: spread evenly
        acc = {r: 1.0 for r in regions}
    total = sum(acc.values()) or 1.0
    out = {k: v / total * (1.0 - FR.CROSS_HERITAGE) for k, v in acc.items()}
    share = FR.CROSS_HERITAGE / len(regions)
    for r in regions:
        out[r] = out.get(r, 0.0) + share
    return sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def identity_of(game: dict) -> str:
    return '|'.join(str(game.get(k) if game.get(k) is not None else '') for k in ('playerid', 'birthdate', 'nationality')) + '|' + gender_code(game.get('gender'))


def _rng(seed: str, identity: str) -> random.Random:
    h = hashlib.sha256(f'{seed}|{identity}'.encode('utf-8')).digest()
    return random.Random(int.from_bytes(h[:8], 'big'))


def choose_face(game: dict, idx: dict, used: set, career_seed: str, overrides: dict | None = None) -> dict | None:
    gender = gender_code(game.get('gender'))
    weights = region_weights(game.get('nationality'), gender, idx, overrides)
    if not weights:
        return None
    identity = identity_of(game)
    rng = _rng(career_seed, identity)
    total = sum(w for _, w in weights)
    x = rng.random() * total
    region = weights[-1][0]
    for r, w in weights:
        x -= w
        if x <= 0:
            region = r
            break
    files = idx[gender][region]
    start = rng.randrange(len(files))
    pick = None
    for i in range(len(files)):
        cand = files[(start + i) % len(files)]
        if cand not in used:
            pick = cand
            break
    if pick is None:  # region exhausted: another likely region for this player before repeating
        for r, w in weights:
            if r == region or w < 0.05 * total:
                continue
            pool = idx[gender][r]
            s0 = rng.randrange(len(pool))
            for i in range(len(pool)):
                cand = pool[(s0 + i) % len(pool)]
                if cand not in used:
                    pick, region = cand, r
                    break
            if pick:
                break
    if pick is None:  # every likely face is in use: repeat one from the chosen region
        pick = files[start]
    return {'file': pick, 'region': region, 'gender': gender, 'source': 'auto', 'identity': identity}


def _valid(face, identity: str, allfiles: dict) -> bool:
    if not isinstance(face, dict) or face.get('identity') != identity:
        return False
    rel = str(face.get('file') or '')
    return bool(rel) and rel in allfiles.get(face.get('gender'), ())


def assign_faces(world: dict, settings: dict | None = None, idx: dict | None = None, choices: dict | None = None) -> dict:
    """Give every tracked player a face from the library. Mutates ``world``.

    Returns counts. Does nothing when the feature is off or no library is set, and
    never removes stored faces in that case (turning the feature back on restores them).
    ``choices`` are the overlay picker's pending choices (see ``load_choices``); the ones
    applied are listed in ``res['applied_choices']`` so the caller can clear them once the
    world has been saved.
    """
    settings = settings if settings is not None else face_settings()
    res = {'enabled': bool(settings.get('face_enabled')), 'assigned': 0, 'kept': 0, 'missing': 0, 'applied_choices': []}
    if not res['enabled']:
        return res
    if idx is None:
        idx = load_library(settings.get('face_library_path'))
    if not idx.get('count'):
        res['missing'] = len(world.get('players') or {})
        return res
    seed = str(world.get('career_uid') or world.get('save_uid') or 'career')
    overrides = _user_overrides()
    players = world.get('players') or {}
    allfiles = {g: {f for files in idx.get(g, {}).values() for f in files} for g in ('M', 'F')}
    for pid, ch in (choices or {}).items():
        p = players.get(str(pid))
        if not p or not isinstance(ch, dict):
            res['applied_choices'].append(str(pid))      # player gone: drop the choice
            continue
        if ch.get('identity') != identity_of(p.get('game') or {}):
            res['applied_choices'].append(str(pid))      # a different person now holds this ID
            continue
        if ch.get('file') == AUTO:
            face = (p.get('engine') or {}).get('face')
            if isinstance(face, dict) and face.get('source') == 'user':
                p['engine'].pop('face', None)
            res['applied_choices'].append(str(pid))
        elif set_user_face(world, str(pid), str(ch.get('file') or ''), idx):
            res['applied_choices'].append(str(pid))
    used = set()
    todo = []
    for key in sorted(players, key=str):
        p = players[key]
        if p.get('retired'):
            continue        # v1.24.36: a retired player's face goes back into the pool
        game = p.get('game') or {}
        eng = p.setdefault('engine', {})
        face = eng.get('face')
        if _valid(face, identity_of(game), allfiles):
            used.add(face['file'])
            res['kept'] += 1
        else:
            todo.append((key, p, game, eng))
    for key, p, game, eng in todo:
        face = choose_face(game, idx, used, seed, overrides)
        if face:
            eng['face'] = face
            used.add(face['file'])
            res['assigned'] += 1
        else:
            res['missing'] += 1
    return res


def set_user_face(world: dict, storage_key: str, rel_file: str, idx: dict) -> bool:
    """Record a face the user picked in the overlay picker."""
    p = (world.get('players') or {}).get(str(storage_key))
    if not p:
        return False
    for g, regions in (('M', idx.get('M', {})), ('F', idx.get('F', {}))):
        for region, files in regions.items():
            if rel_file in files:
                p.setdefault('engine', {})['face'] = {'file': rel_file, 'region': region, 'gender': g, 'source': 'user', 'identity': identity_of(p.get('game') or {})}
                return True
    return False


def face_file(player: dict, settings: dict | None = None) -> Path | None:
    """Absolute path of the player's face, or None when off / not assigned / missing."""
    settings = settings if settings is not None else face_settings()
    if not settings.get('face_enabled') or not settings.get('face_library_path'):
        return None
    face = ((player or {}).get('engine') or {}).get('face')
    if not isinstance(face, dict) or not face.get('file'):
        return None
    p = Path(settings['face_library_path']).expanduser() / Path(str(face['file']))
    return p if p.is_file() else None


# ---------------------------------------------------------------------------
# Overlay face picker (v1.24.32)
# ---------------------------------------------------------------------------
# The bridge is the only writer of the career's world file, and a checkpoint may be
# running when the user picks a face. A pick is therefore stored as a pending choice in
# ``face_choices.json`` beside the world file; the overlay shows it at once and the next
# checkpoint moves it into ``engine.face`` (source "user") and clears it.

AUTO = 'AUTO'
CHOICES_NAME = 'face_choices.json'
PICKER_PAGE = 50   # v1.24.35: faces per batch, fixed for every region and window size
MAX_PICKER_FACES = 950   # the overlay holds 1000 tiles: 950 + the pinned current face, with room to spare


def load_choices(path) -> dict:
    try:
        d = json.loads(Path(path).read_text(encoding='utf-8'))
        return {str(k): v for k, v in d.items() if isinstance(v, dict)} if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_choices(path, d: dict):
    path = Path(path)
    if not d:
        try:
            path.unlink()
        except OSError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, indent=1, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)


def save_choice(path, player: dict, rel_file: str) -> bool:
    """Queue a picked face (or ``AUTO`` to return to the automatic face) for a player."""
    game = (player or {}).get('game') or {}
    pid = game.get('playerid')
    if pid is None or not rel_file:
        return False
    d = load_choices(path)
    d[str(int(pid))] = {'file': str(rel_file), 'identity': identity_of(game)}
    _save_choices(path, d)
    return True


def clear_choices(path, pids) -> None:
    pids = {str(p) for p in pids or ()}
    if not pids:
        return
    d = load_choices(path)
    if any(k in d for k in pids):
        _save_choices(path, {k: v for k, v in d.items() if k not in pids})


def effective_face(world: dict, pid, idx: dict, choices: dict | None = None) -> dict | None:
    """The face the overlay should show now: a pending pick, else the stored face.
    For a pending "automatic" choice the automatic face is worked out the same way the
    next checkpoint will."""
    p = (world.get('players') or {}).get(str(pid))
    if not p:
        return None
    game = p.get('game') or {}
    ident = identity_of(game)
    ch = (choices or {}).get(str(pid))
    stored = (p.get('engine') or {}).get('face')
    if isinstance(ch, dict) and ch.get('identity') == ident:
        if ch.get('file') != AUTO:
            for g in ('M', 'F'):
                for region, files in idx.get(g, {}).items():
                    if ch['file'] in files:
                        return {'file': ch['file'], 'region': region, 'gender': g, 'source': 'user', 'identity': ident}
        else:
            if isinstance(stored, dict) and stored.get('source') != 'user':
                return stored
            used = {f['file'] for k, q in (world.get('players') or {}).items() if str(k) != str(pid) and not q.get('retired')
                    for f in [((q.get('engine') or {}).get('face'))] if isinstance(f, dict) and f.get('file')}
            seed = str(world.get('career_uid') or world.get('save_uid') or 'career')
            return choose_face(game, idx, used, seed, _user_overrides())
    return stored if isinstance(stored, dict) and stored.get('identity') == ident else None


def picker_page(world: dict, pid, idx: dict, region: str = '', limit: int = 0, choices: dict | None = None,
                batch: int = PICKER_PAGE) -> dict | None:
    """The face picker for a player (v1.24.33: one growing list instead of pages).

    Returns the regions (most likely first), the chosen region's first ``limit`` faces,
    which one is current and which are used by other players. ``limit`` <= 0 opens the
    region with one batch. v1.24.35: if the player's current face is further down the region,
    it is shown first (marked current) instead of loading every face up to it.
    """
    p = (world.get('players') or {}).get(str(pid))
    if not p:
        return None
    game = p.get('game') or {}
    gender = gender_code(game.get('gender'))
    regions = [r for r, _w in region_weights(game.get('nationality'), gender, idx, _user_overrides())]
    if not regions:
        return {'gender': gender, 'regions': [], 'region': '', 'shown': 0, 'total': 0, 'faces': [], 'current': None, 'limit': 0}
    batch = max(1, int(batch))
    current = effective_face(world, pid, idx, choices)
    cur_file = (current or {}).get('file')
    if region not in idx[gender]:
        region = (current or {}).get('region') if (current or {}).get('region') in idx[gender] else regions[0]
    files = idx[gender][region]
    if limit <= 0:
        limit = batch
    limit = max(1, min(int(limit), len(files), MAX_PICKER_FACES))
    used = {f['file'] for k, q in (world.get('players') or {}).items() if str(k) != str(pid) and not q.get('retired')
            for f in [((q.get('engine') or {}).get('face'))] if isinstance(f, dict) and f.get('file')}
    for k, ch in (choices or {}).items():
        if str(k) != str(pid) and ch.get('file') not in (None, AUTO):
            used.add(ch['file'])
    chunk = files[:limit]
    shown = len(chunk)
    if cur_file in files and cur_file not in chunk:
        chunk = [cur_file] + chunk          # current face pinned first until "Load more" reaches it
    return {'gender': gender, 'regions': regions, 'region': region, 'shown': shown, 'total': len(files), 'limit': limit,
            'faces': [{'file': f, 'current': f == cur_file, 'in_use': f in used} for f in chunk],
            'current': current}
