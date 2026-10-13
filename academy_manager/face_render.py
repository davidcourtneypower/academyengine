"""Small BMP copies of library faces for the native overlay (v1.24.31).

The overlay draws with plain GDI, so the selected player's face is converted once to a
24-bit BMP flattened onto the overlay's panel colour and cached under
``%LOCALAPPDATA%\\FC27AcademyEngine\\face_cache``. The user's library is only read.
Pillow is used when present; Qt's QImage is the fallback.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from fc27_academy.paths import USER_ROOT

FACE_PX = 96
CACHE_DIR = USER_ROOT / 'face_cache'
CACHE_KEEP = 4000          # ~110 MB of 96 px BMPs; v1.24.35 (was 400, which deleted thumbnails a long list still used)
PRUNE_EVERY = 600.0        # seconds between clean-ups
KEEP_RECENT = 1800.0       # never remove a thumbnail used in the last 30 minutes
_last_prune = 0.0


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = str(hex_colour or '').lstrip('#')
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return 8, 27, 45


def _cache_path(src: Path, bg: str, size: int) -> Path:
    st = src.stat()
    key = f'{src.resolve()}|{st.st_mtime_ns}|{st.st_size}|{bg}|{size}'
    return CACHE_DIR / (hashlib.sha1(key.encode('utf-8')).hexdigest()[:20] + '.bmp')


def _prune(force: bool = False):
    """Remove the least recently used thumbnails beyond CACHE_KEEP, at most every PRUNE_EVERY
    seconds and never one used in the last KEEP_RECENT seconds (a list on screen keeps its files)."""
    global _last_prune
    now = time.time()
    if not force and now - _last_prune < PRUNE_EVERY:
        return
    _last_prune = now
    try:
        files = sorted(((p.stat().st_mtime, p) for p in CACHE_DIR.glob('*.bmp')), reverse=True)
        for mtime, p in files[CACHE_KEEP:]:
            if now - mtime > KEEP_RECENT:
                p.unlink(missing_ok=True)
    except Exception:
        pass


def _render_pillow(src: Path, dst: Path, bg, size: int) -> bool:
    try:
        from PIL import Image
    except Exception:
        return False
    with Image.open(src) as im:
        im = im.convert('RGBA')
        im = im.resize((size, size), Image.LANCZOS)
        base = Image.new('RGBA', (size, size), bg + (255,))
        base.alpha_composite(im)
        tmp = dst.with_suffix('.tmp')
        base.convert('RGB').save(tmp, format='BMP')
        tmp.replace(dst)
    return True


def _render_qt(src: Path, dst: Path, bg, size: int) -> bool:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QImage, QPainter
    except Exception:
        return False
    img = QImage(str(src))
    if img.isNull():
        return False
    img = img.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    out = QImage(size, size, QImage.Format_RGB888)
    out.fill(QColor(*bg))
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    tmp = dst.with_suffix('.tmp.bmp')
    if not out.save(str(tmp), 'BMP'):
        return False
    tmp.replace(dst)
    return True


def overlay_face_bmp(src, bg_hex: str, size: int = FACE_PX) -> Path | None:
    """Cached BMP for ``src`` or None if it cannot be rendered."""
    try:
        src = Path(src)
        if not src.is_file():
            return None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        dst = _cache_path(src, str(bg_hex), size)
        if dst.is_file():
            try:
                os.utime(dst)          # mark as recently used
            except OSError:
                pass
            return dst
        bg = _rgb(bg_hex)
        if _render_pillow(src, dst, bg, size) or _render_qt(src, dst, bg, size):
            _prune()
            return dst
    except Exception:
        return None
    return None
