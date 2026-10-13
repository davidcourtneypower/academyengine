"""v1.24.12 regression: controller settings model, autorun data-root discovery, starting-PlayStyle events."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12412_")

from academy_manager.controller import normalize_combo, combo_mask, settings_view, PRESETS
assert normalize_combo("r3 + l3") == "L3+R3" and normalize_combo("back+rb") == "VIEW+RB" and normalize_combo("A") == "" and normalize_combo("A+Q") == ""
assert combo_mask("L3+R3") == 0x00C0 and combo_mask("LT+RT+VIEW") == 0x30020 and combo_mask("nonsense") == 0x00C0
assert all(normalize_combo(p) == p for p in PRESETS)
assert settings_view({"controller_enabled": False, "controller_combo": "lb+rb+y"}) == (False, "LB+RB+Y", 0x8300)
print("Controller: combo parsing/aliases/validation and XInput masks (incl. LT/RT pseudo-bits): PASS")

# Global settings round-trip through the overlay command path.
import academy_manager.overlay_export as ox
from academy_manager.settings_store import load as load_mgr
assert ox._apply_setting("global", "global", "controller_combo", "VIEW+MENU") and load_mgr()["controller_combo"] == "VIEW+MENU"
assert not ox._apply_setting("global", "global", "controller_combo", "Q+Z") and load_mgr()["controller_combo"] == "VIEW+MENU"
assert ox._apply_setting("global", "global", "controller_enabled", "false") and load_mgr()["controller_enabled"] is False
print("Controller: overlay Settings tab changes persist; invalid combos rejected: PASS")

# Autorun goes to the folder Live Editor loads le_config.json from, not the program folder.
from academy_manager import live_editor_integration as lei
base = Path(tempfile.mkdtemp())
binary = base / "Desktop" / "FC 27 LE v27.1.0"; (binary / "lua").mkdir(parents=True); (binary / "Logs").mkdir()
(binary / "FCLiveEditor.DLL").write_text("x"); (binary / "Launcher.exe").write_text("x")
data = base / "FC 27 Live Editor"; (data / "lua").mkdir(parents=True); (data / "le_config.json").write_text("{}")
(binary / "Logs" / "live_editor_08-10-2026.log").write_text(f"01:00:07.998426\tINFO\tLoad Config From {data}\\le_config.json\n")
lei._registry_data_roots = lambda: []; lei._default_data_roots = lambda: []
assert lei.discover_live_editor_data_root(str(binary), binary_root=binary) == data      # stale saved choice loses
roots = lei.all_live_editor_data_roots(str(binary), binary_root=binary)
res = lei.ensure_autorun_installed(roots[0], roots)
assert res["ok"] and (data / "lua/autorun/FC27_Academy_Engine.lua").exists() and (binary / "lua/autorun/FC27_Academy_Engine.lua").exists(), res
print("Autorun: real data root found from Live Editor's own log; installed there and in the program folder: PASS")

# Starting PlayStyles assigned by the engine become an event and update the player immediately.
from fc27_academy import event_engine
from fc27_academy.paths import ACADEMY_STATE_ROOT
key = "C__b"; wp = ACADEMY_STATE_ROOT / "saves" / key / "generated_world.json"; wp.parent.mkdir(parents=True, exist_ok=True)
wp.write_text(json.dumps({"career": {"user_teamid": 7, "date": {"day": 1, "month": 7, "year": 2026}},
                          "players": {"460008": {"game": {"name": "Youth Player", "clubteamid": 7, "trait1": 0}}}}))
ev = event_engine.record_commit(key, {"status": "COMMITTED", "changeset_id": "cs1", "committed": [
    {"playerid": 460008, "kind": "NEWGEN_ENRICHMENT", "style": "First Touch + Quick Step + Technical", "field": "trait1"}]})
assert ev and ev[0]["title"] == "Starting PlayStyles assigned" and ev[0]["type"] == "PLAYSTYLE_GAINED" and ev[0]["is_user_team"], ev
print("Events: engine-assigned starting PlayStyles are recorded as a PlayStyle event for the user's team: PASS")
