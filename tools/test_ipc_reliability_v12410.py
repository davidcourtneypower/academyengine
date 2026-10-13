"""v1.24.10 regression: Windows sharing retries, career-bound commands, command queue."""
from __future__ import annotations
import os, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12410_ipc_")

# 1. replace_retry survives a transient sharing violation and still raises real errors.
import fc27_academy.fsutil as fsutil
real = os.replace; calls = {"n": 0}
def flaky(a, b):
    calls["n"] += 1
    if calls["n"] < 4: raise PermissionError(5, "Access is denied")
    return real(a, b)
d = Path(tempfile.mkdtemp()); src = d / "a.tmp"; dst = d / "a"
src.write_text("x"); fsutil.os.replace = flaky
try: fsutil.replace_retry(src, dst)
finally: fsutil.os.replace = real
assert dst.read_text() == "x" and calls["n"] == 4
try:
    fsutil.replace_retry(d / "missing", d / "b"); raise AssertionError("missing source should raise")
except FileNotFoundError: pass
print("fsutil: transient WinError 5 retried to success; genuine errors still raised: PASS")

# 2. Commands issued from the last READY generation are applied while FC27 advances.
from fc27_academy.transaction_store import set_lifecycle, publish_generation
from fc27_academy.branch_identity import write_active_context
from fc27_academy.paths import BRIDGE_ROOT, ensure_dirs
import academy_manager.overlay_export as ox
ensure_dirs()
write_active_context(BRIDGE_ROOT, career_uid="C", branch_id="b", storage_key="C__b", runtime_session="S")
gen = publish_generation("payload", runtime_session="S", career_uid="C", storage_key="C__b", request_id="r", career_date={}, promote=False)
set_lifecycle("READY", career_uid="C", storage_key="C__b", generation=gen)
set_lifecycle("ADVANCING", generation=0)            # what the bridge does on DAY_PASSED
def cmd(name, text):
    (BRIDGE_ROOT / name).write_text(text, encoding="utf-8")
cmd("overlay_cmd_0001.txt", f"GEN|{gen}\nVIEW|query|smith\n")
cmd("overlay_cmd_0002.txt", f"GEN|{gen}\nSELECT|460123\n")             # two clicks inside one poll
cmd("overlay_cmd_0003.txt", f"GEN|{gen}\nACTION|clear_logs\n")          # destructive: must wait for exact READY
assert ox.process_overlay_command() is True
v = ox._load_view("C__b")
assert v.get("query") == "smith" and v.get("selected_pid") == 460123, v
assert ox._advance_view_dirty is True and not list(BRIDGE_ROOT.glob("overlay_cmd_*.txt"))
print("Commands: view + selection from the browseable generation applied during ADVANCING; both queued clicks kept: PASS")

# A different career's generation is rejected; RECONCILING keeps the command queued.
gen2 = publish_generation("other", runtime_session="S", career_uid="D", storage_key="D__x", request_id="r2", career_date={}, promote=False)
cmd("overlay_cmd_0004.txt", f"GEN|{gen2}\nVIEW|query|other\n")
assert ox.process_overlay_command() is False and ox._load_view("C__b").get("query") == "smith"
set_lifecycle("RECONCILING")
cmd("overlay_cmd_0005.txt", f"GEN|{gen}\nVIEW|query|later\n")
assert ox.process_overlay_command() is False and (BRIDGE_ROOT / "overlay_cmd_0005.txt").exists()
set_lifecycle("READY", generation=gen)
assert ox.process_overlay_command() is True and ox._load_view("C__b").get("query") == "later"
print("Commands: other-career generation rejected; command waits through RECONCILING and applies at READY: PASS")

# 3. End-to-end with the real exporter: a filter applied while ADVANCING is republished
#    from the last reconciled world, without promoting the lifecycle back to READY.
import json as _json
from unittest.mock import patch
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle
svc = BridgeService(FileBridge())
for i, fn in enumerate(["01_load.json", "02_day_growth.json"]):
    obj = _json.loads((ROOT / "tests/fixtures" / fn).read_text()); p = obj.get("payload") or obj
    p["runtime_session"] = "advtest"; p["checkpoint_id"] = f"adv{i}"
    res = svc.handle(BridgeRequest(f"adv{i}", "CHECKPOINT_SNAPSHOT", p)); assert res["status"] == "OK"
with patch.object(ox, "detect_game", return_value=True), patch.object(ox, "game_pid", return_value=123):
    ox._last_publication_revision = None
    assert ox.publish_overlay_state({"state": "IDLE"}) and lifecycle()["state"] == "READY"
    g = lifecycle()["generation"]
    set_lifecycle("ADVANCING", generation=0)
    ox._advance_view_dirty = False          # part 2 above left a pending view change
    before = ox.STATE_FILE.read_text()
    assert not ox.publish_overlay_state({"state": "IDLE"}) or ox.STATE_FILE.read_text() == before   # nothing new to show
    cmd("overlay_cmd_0100.txt", f"GEN|{g}\nVIEW|query|Test Player 3\n")
    assert ox.process_overlay_command() is True
    assert ox.publish_overlay_state({"state": "IDLE"})
    after = ox.STATE_FILE.read_text()
    assert "FILTER_QUERY=Test Player 3" in after and lifecycle()["state"] == "ADVANCING", (lifecycle()["state"],)
    newgen = int(after.split("MODEL_GENERATION=")[1].split("\n")[0])
    cmd("overlay_cmd_0101.txt", f"GEN|{newgen}\nVIEW|query|Test Player 4\n")      # follow-up click from the new view
    assert ox.process_overlay_command() is True
print("Exporter: filter applied during ADVANCING republished from last reconciled world; lifecycle stays ADVANCING; follow-up click accepted: PASS")
