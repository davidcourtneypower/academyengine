"""v1.0.3 regressions.

1. "Delete current career engine data" removes every branch of the loaded career (files,
   stored checkpoints, save anchors, game snapshots, read generations, overlay cache); the
   overlay empties at once; another career is untouched; the career is rebuilt at the next
   checkpoint with its players as already known (no second round of starting PlayStyles).
2. Live Editor's log folder is found without the program folder (data folders, remembered path).
3. The launcher says when the log cannot be found.
"""
from __future__ import annotations
import json, os, re, shutil, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v103_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle, _connect
from fc27_academy.paths import ACADEMY_STATE_ROOT, EVENTS_ROOT, BRIDGE_ROOT, DELETED_CAREERS_ROOT
from academy_manager import overlay_export as ex, read_model
from academy_manager.live_data import active_world, active_context
ex.detect_game = lambda *a, **k: True; ex.game_pid = lambda *a, **k: 4242

base = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = base.get("payload") or base
grown = json.loads((ROOT / "tests/fixtures/02_day_growth.json").read_text()); grown = grown.get("payload") or grown
svc = BridgeService(FileBridge())
def cp(p, i, trig, uid="TESTSAVE"):
    r = svc.handle(BridgeRequest(f"r{uid}{i}", "CHECKPOINT_SNAPSHOT", dict(p, save_uid=uid, runtime_session="RS", day_epoch=i, checkpoint_id=f"{uid}c{i}", trigger=trig)))
    assert r["status"] == "OK", r; return r
# another career first (must survive), then the one we delete
cp(base, 0, "CAREER_SETTLED_BASELINE", uid="OTHERCAREER"); cp(grown, 1, "DAY_SETTLED", uid="OTHERCAREER")
other_key = active_context()["storage_key"]
cp(base, 0, "CAREER_SETTLED_BASELINE"); cp(grown, 1, "DAY_SETTLED")
key = active_context()["storage_key"]; uid = "TESTSAVE"
assert key.startswith(uid) and other_key.startswith("OTHERCAREER")
# a second branch of the same career on disk (e.g. from Save As / an older save)
branch2 = f"{uid}__branch__b_second"
shutil.copytree(ACADEMY_STATE_ROOT / "saves" / key, ACADEMY_STATE_ROOT / "saves" / branch2)
seq = [0]
def command(body):
    seq[0] += 1; g = int(lifecycle()["generation"])
    (ex.BRIDGE_ROOT / f"overlay_cmd_{seq[0]:010d}_{seq[0]:06d}.txt").write_text(f"GEN|{g}\n{body}\n")
    r = ex.process_overlay_command(); ex.publish_overlay_state({}); return r
ex.publish_overlay_state({})
def rows(): return len(re.findall(r"^4600\d\d\|", ex.STATE_FILE.read_text(), re.M))
assert rows() == 5
def db_count(table, k):
    with _connect() as con: return con.execute(f"SELECT count(*) FROM {table} WHERE storage_key=? OR career_uid=?", (k, k.split("__")[0])).fetchone()[0]
assert db_count("academy_checkpoints", key) > 0 and db_count("academy_checkpoints", other_key) > 0

assert command("ACTION|delete_current_data")
assert rows() == 0, "overlay still shows the deleted career"
life = lifecycle()
assert life["state"] == "CAREER_LOADING" and "deleted" in life["detail"] and int(life["generation"]) == 0, life
for k in (key, branch2):
    assert not (ACADEMY_STATE_ROOT / "saves" / k).exists() and not (EVENTS_ROOT / k).exists() and not (BRIDGE_ROOT / "saves" / k).exists(), k
for t in ("academy_checkpoints", "save_anchors", "game_snapshots", "read_generations"):
    assert db_count(t, key) == 0, t
assert (ACADEMY_STATE_ROOT / "saves" / other_key / "generated_world.json").exists() and db_count("academy_checkpoints", other_key) > 0
assert (DELETED_CAREERS_ROOT / f"{uid}.json").exists()
print("Delete: every branch, stored checkpoints/anchors/snapshots and overlay cache removed; overlay empties at once; other careers untouched: PASS")

r = cp(grown, 2, "DAY_SETTLED")
w = active_world()
assert len(w["players"]) == 5 and all(p.get("bootstrap_source") == "REBUILT_AFTER_DELETE" for p in w["players"].values())
assert not any(p.get("generation_new_this_checkpoint") for p in w["players"].values())
assert int((r["payload"].get("newgen_enrichment") or {}).get("enrichment_proposals") or 0) == 0
assert max(float(v or 0) for p in w["players"].values() for v in ((p.get("engine") or {}).get("playstyle_progress") or {"x": 0}).values()) == 0.0
ex.publish_overlay_state({}); assert rows() == 5
print("Rebuild: players come back from FC27 at the next checkpoint as already known, progress from zero, no starting PlayStyles again: PASS")

# ---- 2. log folder ----------------------------------------------------------------------------------
from academy_manager import le_menu_watch as M, live_editor_integration as LEI
from academy_manager.settings_store import load as load_settings, save as save_settings
data_root = Path(tempfile.mkdtemp()) / "FC 27 Live Editor"; (data_root / "lua").mkdir(parents=True); (data_root / "le_config.json").write_text("{}")
LEI.discover_live_editor_root = lambda *a, **k: None                 # program folder hidden (Live Editor elevated)
save_settings({"live_editor_data_root": str(data_root)})
assert M.find_logs_dir() is None                                      # no Logs anywhere yet
(data_root / "Logs").mkdir(); (data_root / "Logs" / "le_2026.log").write_text("x")
assert M.find_logs_dir() == data_root / "Logs"
assert load_settings().get("live_editor_logs") == str(data_root / "Logs")
s = load_settings(); s.pop("live_editor_data_root"); save_settings(s)
assert M.find_logs_dir() == data_root / "Logs", "remembered log folder not used"
print("Log folder: found in Live Editor's data folder without the program folder, and remembered: PASS")

# ---- 3. launcher warning ------------------------------------------------------------------------------
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from academy_manager import launcher as L
for n in ("start_engine", "stop_engine", "stop_overlay_host", "clear_live_session_markers", "ensure_running"):
    setattr(L, n, lambda *a, **k: None)
L.engine_health = lambda *a, **k: {"running": True}
L.ensure_overlay_host = lambda *a, **k: {"ok": True, "heartbeat": True}
L.detect_game = lambda *a, **k: True
L.elevation_mismatch = lambda: False
L.ensure_autorun_installed = lambda data, extra=(): {"ok": True, "updated": False}
L.discover_live_editor_data_root = lambda *a, **k: data_root
found = {"v": None}
M.find_logs_dir = lambda: found["v"]
win = L.Launcher(); win.timer.stop()
win._next_logs_check = 0; win.poll()
assert "Live Editor log not found" in win.integration.text(), win.integration.text()
assert win.integration.text().startswith("Live Editor bridge: ready")
found["v"] = data_root / "Logs"; win._next_logs_check = 0; win.poll()
assert "Live Editor log not found" not in win.integration.text()
print("Launcher: says when Live Editor's log cannot be found; message clears once it is: PASS")
print("FC27 Academy Engine v1.0.3 regression: PASS")
