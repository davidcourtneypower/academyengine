"""Live-readable Academy Engine tuning.

The GUI writes academy_settings.json in the stable LOCALAPPDATA config folder. Production code reads
through this module so safe tuning changes (cooldowns, progression multipliers,
thresholds and output throughput) take effect on the next checkpoint without
restarting the bridge.
"""
from __future__ import annotations
import os
import json, time
from pathlib import Path
from .paths import PROJECT_ROOT, CONFIG_ROOT, USER_ROOT, BRIDGE_ROOT

ROOT = PROJECT_ROOT
SETTINGS_PATH = CONFIG_ROOT / "academy_settings.json"
DEFAULTS_PATH = ROOT / "data" / "academy_settings.default.json"
_CACHE = None
_CACHE_MTIME = None
_CACHE_AT = 0.0
_CAREER_SETTINGS_ROOT = USER_ROOT / 'engine_data' / 'career_settings'


def _merge(a, b):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return b
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if k in out and isinstance(out[k], dict) and isinstance(v, dict) else v
    return out


def _active_storage_key() -> str:
    p = BRIDGE_ROOT / "active_context.lua"
    if not p.exists():
        return ""
    try:
        import re
        m = re.search(r'storage_key="([^"]*)"', p.read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except Exception:
        return ""


BRANCH_SEPARATOR = '__branch__'


def _safe_name(key: str) -> str:
    return ''.join(c if c.isalnum() or c in ('-','_') else '_' for c in str(key))


def settings_career_key(storage_key: str) -> str:
    """The career a storage branch belongs to (v1.24.22).

    Settings are user policy, not career state: every branch of one FC27 save
    (rewinds, reloads after quitting without saving) shares one settings file, so a
    change is never undone by loading an older point of the same career.
    """
    return str(storage_key or '').split(BRANCH_SEPARATOR, 1)[0]


def settings_file(root: Path, storage_key: str) -> Path:
    """Career-level settings file under `root`, migrating per-branch files once.

    v1.24.21 and earlier kept one file per branch; the most recently changed branch
    file of the career seeds the shared file the first time it is needed.
    """
    root = Path(root); career = _safe_name(settings_career_key(storage_key))
    target = root / f"{career}.json"
    if not target.exists() and career:
        try:
            legacy = sorted(root.glob(f"{career}{BRANCH_SEPARATOR}*.json"), key=lambda p: p.stat().st_mtime_ns)
        except OSError:
            legacy = []
        if legacy:
            try:
                import shutil
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(legacy[-1], target)
            except OSError:
                pass
    return target


def career_settings_path(storage_key: str | None = None) -> Path | None:
    key = storage_key or _active_storage_key()
    if not key:
        return None
    return settings_file(_CAREER_SETTINGS_ROOT, key)


def load_runtime_settings(force: bool = False) -> dict:
    global _CACHE, _CACHE_MTIME, _CACHE_AT
    now = time.monotonic()
    # v1.24.10: serve the cache without touching the filesystem for up to 1s.
    # Every progression helper reads settings, and v1.24.09 re-read
    # active_context.lua plus two stat() calls ~60,000 times per checkpoint.
    if not force and _CACHE is not None and (now - _CACHE_AT) < 1.0:
        return _CACHE
    cpath = career_settings_path()
    try:
        gm = SETTINGS_PATH.stat().st_mtime_ns if SETTINGS_PATH.exists() else -1
    except OSError:
        gm = -1
    try:
        cm = cpath.stat().st_mtime_ns if cpath and cpath.exists() else -1
    except OSError:
        cm = -1
    sig = (gm, str(cpath or ''), cm)
    if not force and _CACHE is not None and sig == _CACHE_MTIME:
        # Files unchanged: restart the no-IO window instead of re-checking per call.
        _CACHE_AT = now
        return _CACHE
    try:
        defaults = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        defaults = {}
    data = defaults
    if SETTINGS_PATH.exists():
        try:
            data = _merge(data, json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    if cpath and cpath.exists():
        try:
            data = _merge(data, json.loads(cpath.read_text(encoding="utf-8")))
        except Exception:
            pass
    _CACHE, _CACHE_MTIME, _CACHE_AT = data, sig, now
    return data


def production() -> dict:
    return load_runtime_settings().get("production", {})


def development() -> dict:
    return load_runtime_settings().get("development", {})


def decline() -> dict:
    """v1.24.36: PlayStyle decline with age (both switches off by default)."""
    d = dict(load_runtime_settings().get("decline", {}) or {})
    cap = 100.0 if _debug() else 10.0
    try:
        d["decline_speed"] = max(0.10, min(cap, float(d.get("decline_speed", 1.0))))
    except (TypeError, ValueError):
        d["decline_speed"] = 1.0
    d["playstyle_loss_enabled"] = bool(d.get("playstyle_loss_enabled", False))
    d["playstyle_plus_loss_enabled"] = bool(d.get("playstyle_plus_loss_enabled", False))
    return d


def normal_cooldown_days() -> int:
    return max(0, min(365, int(production().get("normal_playstyle_cooldown_days", 120))))


def plus_cooldown_days() -> int:
    return max(0, min(720, int(production().get("playstyle_plus_cooldown_days", 180))))


def role_cooldown_days() -> int:
    return max(0, min(365, int(production().get("role_upgrade_cooldown_days", 120))))


def debug_mode_available() -> bool:
    """v1.24.38: debug / stress-test mode is a developer tool, hidden unless FC27AE_DEBUG=1."""
    return os.environ.get("FC27AE_DEBUG") == "1"


def _debug() -> bool:
    return debug_mode_available() and bool(production().get("debug_stress_mode", False))


def normal_threshold() -> float:
    # v1.24.28: debug / stress-test mode allows much lower progress targets.
    return max(10.0 if _debug() else 50.0, min(200.0, float(production().get("normal_playstyle_threshold", 100.0))))


def plus_threshold() -> float:
    configured = max(10.0 if _debug() else 100.0, min(360.0, float(production().get("playstyle_plus_threshold", 180.0))))
    # Fail safe even if somebody edits JSON outside the GUI: PS+ must never
    # become easier than acquiring a normal PlayStyle.
    return max(normal_threshold(), configured)


def normal_progress_multiplier() -> float:
    return max(0.10, min(100.0 if _debug() else 10.0, float(development().get("playstyle_progression_speed", 1.0))))


def plus_progress_multiplier() -> float:
    return max(0.10, min(100.0 if _debug() else 10.0, float(development().get("playstyle_plus_progression_speed", 1.0))))


def role_progress_multiplier() -> float:
    return max(0.10, min(100.0 if _debug() else 10.0, float(development().get("role_progression_speed", 1.0))))



def plus_eligibility_multiplier() -> float:
    return max(0.0, min(5.0, float(development().get("playstyle_plus_eligibility_multiplier", 1.0))))

def debug_stress_mode() -> bool:
    return _debug()

def newgen_per_checkpoint() -> int:
    cap=500 if debug_stress_mode() else 50
    return max(0, min(cap, int(production().get("newgen_enrichment_per_checkpoint", 4))))

def max_total_changes_per_checkpoint() -> int:
    return max(4, min(512 if debug_stress_mode() else 64, int(production().get("max_total_changes_per_checkpoint", 12))))

def max_normal_per_checkpoint() -> int:
    return max(0, min(512 if debug_stress_mode() else 64, int(production().get("max_normal_playstyles_per_checkpoint", 6))))

def max_plus_per_checkpoint() -> int:
    return max(0, min(512 if debug_stress_mode() else 64, int(production().get("max_playstyle_plus_per_checkpoint", 3))))

def max_role_transactions_per_checkpoint() -> int:
    return max(0, min(512 if debug_stress_mode() else 64, int(production().get("max_role_transactions_per_checkpoint", 3))))



def prioritize_user_team_processing() -> bool:
    return bool(production().get("prioritize_user_team_processing", True))
