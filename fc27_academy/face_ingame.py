"""Experimental: write library faces as Live Editor minifaces (v1.24.31, off by default).

Live Editor serves legacy miniface overrides from

    <Live Editor folder>\\mods\\legacy\\data\\ui\\imgAssets\\heads\\p<playerid>.dds
    <Live Editor folder>\\mods\\legacy\\data\\ui\\imgAssets\\youthheads\\p<playerid>.dds

Live Editor 27.1.x shows such files in its own editor but not yet in-game for
generated players, so the setting "Write faces into FC27" ships switched off.

Player IDs are reused between careers, so the folder always mirrors the career that
is loaded: faces for its tracked players are written, and faces written earlier for
other players are removed. A manifest records every file this module wrote together
with a hash of the bytes; a file is only replaced or deleted while it still holds
exactly those bytes, so minifaces the user imported themselves are never touched.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path

from .paths import USER_ROOT

MANIFEST = USER_ROOT / 'face_ingame_manifest.json'
SUBDIRS = ('heads', 'youthheads')
DDS_PX = 256


def target_dirs(roots) -> list[Path]:
    """imgAssets folders under the Live Editor root(s). Roots with a mods folder win."""
    seen, with_mods, rest = set(), [], []
    for r in roots or ():
        if not r:
            continue
        r = Path(r)
        k = str(r).lower()
        if k in seen:
            continue
        seen.add(k)
        (with_mods if (r / 'mods').is_dir() else rest).append(r)
    chosen = with_mods or rest[:1]
    return [r / 'mods' / 'legacy' / 'data' / 'ui' / 'imgAssets' for r in chosen]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _file_sha(p: Path) -> str | None:
    try:
        return _sha(p.read_bytes())
    except OSError:
        return None


def _load_manifest() -> dict:
    try:
        d = json.loads(MANIFEST.read_text(encoding='utf-8'))
        return d if isinstance(d.get('files'), dict) else {'files': {}}
    except Exception:
        return {'files': {}}


def _save_manifest(m: dict):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix('.tmp')
    tmp.write_text(json.dumps(m, indent=1, sort_keys=True), encoding='utf-8')
    os.replace(tmp, MANIFEST)


def encode_dds(src: Path, size: int = DDS_PX) -> bytes | None:
    """DXT5 DDS bytes for ``src`` (needs Pillow 10+). None when unavailable."""
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        with Image.open(src) as im:
            im = im.convert('RGBA').resize((size, size), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format='DDS', pixel_format='DXT5')
            return buf.getvalue()
    except Exception:
        return None


def sync(world: dict, library_root, roots, *, enabled: bool) -> dict:
    """Mirror the loaded career's faces into Live Editor's miniface folders."""
    res = {'written': 0, 'kept': 0, 'removed': 0, 'skipped_user_files': 0, 'errors': 0, 'reason': ''}
    manifest = _load_manifest()
    files = manifest['files']
    wanted: dict[str, tuple[Path, str]] = {}
    dirs = target_dirs(roots)
    if enabled and library_root and dirs:
        lib = Path(str(library_root))
        for key, p in (world.get('players') or {}).items():
            if p.get('retired'):
                continue
            face = ((p.get('engine') or {}).get('face')) or {}
            pid = (p.get('game') or {}).get('playerid') or key
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                continue
            if not face.get('file'):
                continue
            src = lib / Path(str(face['file']))
            for d in dirs:
                for sub in SUBDIRS:
                    wanted[str(d / sub / f'p{pid}.dds')] = (src, str(face['file']))
    elif enabled and not dirs:
        res['reason'] = 'LIVE_EDITOR_FOLDER_UNKNOWN'

    # Remove our own files that the loaded career no longer wants.
    for path in list(files):
        if path in wanted:
            continue
        p = Path(path)
        cur = _file_sha(p)
        if cur is None:
            files.pop(path, None)
        elif cur == files[path].get('sha'):
            try:
                p.unlink()
                files.pop(path, None)
                res['removed'] += 1
            except OSError:
                res['errors'] += 1
        else:  # the user replaced it: no longer ours
            files.pop(path, None)

    encoded: dict[str, bytes | None] = {}
    for path, (src, rel) in wanted.items():
        p = Path(path)
        rec = files.get(path)
        cur = _file_sha(p)
        if cur is not None and (rec is None or cur != rec.get('sha')):
            res['skipped_user_files'] += 1   # not written by us (or changed since): leave it
            files.pop(path, None)
            continue
        if rec and cur == rec.get('sha') and rec.get('src') == rel:
            res['kept'] += 1
            continue
        if src not in encoded:
            encoded[src] = encode_dds(src)
        data = encoded[src]
        if data is None:
            res['errors'] += 1
            res['reason'] = res['reason'] or 'PILLOW_OR_IMAGE_UNAVAILABLE'
            continue
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix('.ae_tmp')
            tmp.write_bytes(data)
            os.replace(tmp, p)
            files[path] = {'sha': _sha(data), 'src': rel}
            res['written'] += 1
        except OSError:
            res['errors'] += 1
    try:
        _save_manifest(manifest)
    except OSError:
        res['errors'] += 1
    return res
