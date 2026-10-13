from __future__ import annotations
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def _local_appdata_root() -> Path:
    env = os.getenv("LOCALAPPDATA")
    if env:
        return Path(env)
    return Path.home() / ".local" / "share"

USER_ROOT = _local_appdata_root() / "FC27AcademyEngine"
ENGINE_DATA_ROOT = USER_ROOT / "engine_data"
ACADEMY_STATE_ROOT = ENGINE_DATA_ROOT / "academy_state"
DELETED_CAREERS_ROOT = ENGINE_DATA_ROOT / "deleted_careers"   # v1.0.3: careers whose engine data was deleted
EVENTS_ROOT = ENGINE_DATA_ROOT / "events"
CONFIG_ROOT = USER_ROOT / "config"
LOG_ROOT = USER_ROOT / "logs"
CACHE_ROOT = USER_ROOT / "cache"
RUNTIME_ROOT = USER_ROOT / "runtime"
BRIDGE_ROOT = RUNTIME_ROOT / "bridge"

def ensure_dirs() -> None:
    for p in (
        USER_ROOT, ENGINE_DATA_ROOT, ACADEMY_STATE_ROOT, EVENTS_ROOT,
        CONFIG_ROOT, LOG_ROOT, CACHE_ROOT, RUNTIME_ROOT, BRIDGE_ROOT, BRIDGE_ROOT / "responses",
        BRIDGE_ROOT / "saves", BRIDGE_ROOT / "branch_hints", BRIDGE_ROOT / "request_files",
    ):
        p.mkdir(parents=True, exist_ok=True)
