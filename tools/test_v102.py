"""v1.0.2: the launcher has no Live Editor folder pickers. Until Live Editor has run once it says
to start FC27 through Live Editor, and it finds Live Editor by itself (retrying every 5 s)."""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v102_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
app = QApplication.instance() or QApplication([])
from academy_manager import launcher as L
from academy_manager.settings_store import load as load_settings
for n in ("start_engine", "stop_engine", "stop_overlay_host", "clear_live_session_markers", "ensure_running"):
    setattr(L, n, lambda *a, **k: None)
L.engine_health = lambda *a, **k: {"running": True}
L.detect_game = lambda *a, **k: False
le = {"binary": None, "data": None}
calls = []
L.discover_live_editor_root = lambda *a, **k: le["binary"]
L.discover_live_editor_data_root = lambda *a, **k: le["data"]
L.all_live_editor_data_roots = lambda *a, **k: [le["data"]] if le["data"] else []
def fake_install(data, extra=()):
    calls.append(data)
    return {"ok": True, "updated": False, "path": str(Path(data) / "lua/autorun/x.lua")} if data else {"ok": False, "reason": "LIVE_EDITOR_DATA_ROOT_UNKNOWN"}
L.ensure_autorun_installed = fake_install
clock = {"t": 1000.0}
L.time.monotonic = lambda: clock["t"]

win = L.Launcher(); win.timer.stop()
labels = " ".join(w.text() for w in win.findChildren(QLabel))
buttons = " ".join(b.text() for b in win.findChildren(QPushButton))
assert "Live Editor locations" not in labels and "Browse binary" not in buttons and "Browse data" not in buttons, (labels[:200], buttons)
assert not hasattr(win, "choose_live_editor_binary") and not hasattr(win, "_le_card")
msg = win.integration.text()
assert "not set up yet" in msg and "Start FC27 through Live Editor at least once" in msg, msg
print("Launcher: no Live Editor locations section; message says to start FC27 through Live Editor once: PASS")

n = len(calls); win.poll(); win.poll()
assert len(calls) == n, "detection retried more often than every 5 s"
data = Path(tempfile.mkdtemp()) / "FC 27 Live Editor"; data.mkdir()
le["data"] = data; le["binary"] = data
clock["t"] += 5.1; win.poll()
assert win.integration.text().startswith("Live Editor bridge: ready") and str(data) in win.integration.text(), win.integration.text()
s = load_settings(); assert s.get("live_editor_data_root") == str(data) and s.get("live_editor_root") == str(data)
n = len(calls); clock["t"] += 60; win.poll()
assert len(calls) == n, "detection keeps running after the bridge is ready"
le["binary"] = None                                                     # program folder unknown: still ready (only the data folder is needed)
win2 = L.Launcher(); win2.timer.stop()
assert win2.integration.text().startswith("Live Editor bridge: ready")
print("Detection: retried every 5 s until Live Editor is found, then remembered; ready even without the program folder: PASS")
print("FC27 Academy Engine v1.0.2 regression: PASS")
