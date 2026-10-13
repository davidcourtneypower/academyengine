"""v1.24.28 regressions: returning to FC27's main menu (seen only in Live Editor's log)
detaches the career; it stays detached until the Lua runtime reports a new career load."""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12428_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from academy_manager.le_menu_watch import MenuWatch, MENU_MARKER
logs = Path(tempfile.mkdtemp()); f1 = logs / "live_editor_09-10-2026.log"
f1.write_bytes(b"old\n" + MENU_MARKER + b"\n")                       # history before the bridge started
t = [0.0]; w = MenuWatch(lambda: logs, clock=lambda: t[0], poll_interval=0.5)
def step(): t[0] += 1.0; return w.poll()
assert step() is False                                                 # history ignored
with open(f1, "ab") as fh: fh.write(b"17:47:38 [LUA API] FC27AE_EVENT ev=28.0\n")
assert step() is False
with open(f1, "ab") as fh: fh.write(b"17:47:42\tINFO\t[LE::UnsupportedLeag")    # marker split across writes
assert step() is False
with open(f1, "ab") as fh: fh.write(b"uesManager::Load] Start\n")
assert step() is True and step() is False                              # reported once
time.sleep(0.02); f2 = logs / "live_editor_10-10-2026.log"; f2.write_bytes(MENU_MARKER + b"\n")
os.utime(f2, (time.time() + 5, time.time() + 5))
assert step() is True                                                  # new day's log read from its start
t2 = [0.0]; w2 = MenuWatch(lambda: None, clock=lambda: t2[0]); t2[0] = 1; assert w2.poll() is False
print("Main-menu watch: new Live Editor log lines only, split lines, log rotation, no log folder: PASS")

import run_bridge_service as rbs
from fc27_academy.transaction_store import set_lifecycle, lifecycle
bridge = Path(tempfile.mkdtemp()); marker = bridge / "resident_runtime_status.json"
marker.write_text(json.dumps({"state": "ACTIVE", "save_uid": "C1"}))
set_lifecycle("READY", detail="x", runtime_session="s", career_uid="C1", storage_key="C1__branch__a", branch_id="a", request_id="r", career_date={}, snapshot_sequence=1, generation=3)
assert rbs._main_menu_guard(bridge, False) is False and lifecycle()["state"] == "READY"
assert rbs._main_menu_guard(bridge, True) is True and lifecycle()["state"] == "DETACHED" and not lifecycle().get("career_uid")
# a checkpoint finishing after the menu appeared does not bring the career back
set_lifecycle("READY", detail="late", runtime_session="s", career_uid="C1", storage_key="C1__branch__a", branch_id="a", request_id="r2", career_date={}, snapshot_sequence=2, generation=4)
assert rbs._main_menu_guard(bridge, False) is True and lifecycle()["state"] == "DETACHED"
# the next career load (Lua writes a new runtime status) ends the guard
time.sleep(0.02); marker.write_text(json.dumps({"state": "LEFT_CAREER", "save_uid": "DEFERRED"})); os.utime(marker, None)
set_lifecycle("CAREER_LOADING", detail="loading", runtime_session="s", career_uid="C1", storage_key="", branch_id="", request_id="", career_date={}, snapshot_sequence=0, generation=0)
assert rbs._main_menu_guard(bridge, False) is False and lifecycle()["state"] == "CAREER_LOADING"
src = (ROOT / "run_bridge_service.py").read_text(encoding="utf-8")
assert src.count("_main_menu_guard(Path(bridge.root)") == 2 and "menu_watch.poll()" in src
print("Bridge: main menu detaches the career and keeps it detached until the next career load: PASS")
print("FC27 Academy Engine v1.24.28 regression: PASS")
