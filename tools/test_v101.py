"""v1.0.1 regressions: FC27 running as administrator while Academy Engine is not.

1. The restart command uses the windowless Python and tells the new launcher which one to wait for.
2. relaunch_elevated: UAC accepted / refused / failed.
3. wait_for_pid waits for the old launcher (and gives up after the timeout).
4. run_manager waits before its single-instance check when restarted.
5. Launcher: the button appears only with a mismatch; "always" restarts once per session;
   a refused prompt keeps the launcher running with a clear message; a started restart closes it.
"""
from __future__ import annotations
import os, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v101_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from academy_manager import elevation as E

# ---- 1. restart command ---------------------------------------------------------------------------
d = Path(tempfile.mkdtemp()); (d / "python.exe").write_text("x"); (d / "pythonw.exe").write_text("x")
real = sys.executable
try:
    sys.executable = str(d / "python.exe")
    prog, params, folder = E.restart_command(4321)
finally:
    sys.executable = real
assert prog == str(d / "pythonw.exe"), prog
assert params == f'"{ROOT / "run_manager.py"}" --wait-for-pid 4321' and folder == str(ROOT), params
print("Restart command: windowless Python, run_manager.py, waits for the old launcher: PASS")

# ---- 2. relaunch ------------------------------------------------------------------------------------
calls = []
def fake(rc):
    def f(hwnd, verb, prog, params, folder, show):
        calls.append(verb); return rc
    return f
ok, msg = E.relaunch_elevated(99, shell_execute=fake(42)); assert ok and calls[-1] == "runas", msg
ok, msg = E.relaunch_elevated(99, shell_execute=fake(5)); assert not ok and "permission was not given" in msg, msg
ok, msg = E.relaunch_elevated(99, shell_execute=fake(2)); assert not ok and "error 2" in msg, msg
def boom(*a): raise OSError("no shell")
ok, msg = E.relaunch_elevated(99, shell_execute=boom); assert not ok and "no shell" in msg, msg
print("Relaunch: UAC accepted starts the restart; refused or failed keeps running with a message: PASS")

# ---- 3. wait_for_pid -----------------------------------------------------------------------------------
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.2)"])
t = time.monotonic(); assert E.wait_for_pid(p.pid, timeout=10) and time.monotonic() - t >= 0.8
p.wait()
assert E.wait_for_pid(999999, timeout=1)                         # already gone
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
t = time.monotonic(); E.wait_for_pid(p.pid, timeout=0.5); assert time.monotonic() - t < 3
p.kill(); p.wait()
print("wait_for_pid: waits for the old launcher, returns at once if gone, gives up after the timeout: PASS")

# ---- 4. run_manager waits before the single-instance check ----------------------------------------------
src = (ROOT / "run_manager.py").read_text(encoding="utf-8")
assert src.index("_wait_for_previous_launcher()\nif _already_running():") > 0
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.2)"])
prefix = src.split("if _already_running():")[0]
saved = list(sys.argv); sys.argv = ["run_manager.py", "--wait-for-pid", str(p.pid)]
try:
    t = time.monotonic(); exec(compile(prefix, str(ROOT / "run_manager.py"), "exec"), {"__file__": str(ROOT / "run_manager.py")})
    waited = time.monotonic() - t
finally:
    sys.argv = saved
p.wait()
assert waited >= 0.8, waited
print("run_manager: a restarted launcher waits for the old one before the single-instance check: PASS")

# ---- 5. launcher ------------------------------------------------------------------------------------------
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from academy_manager import launcher as L
from academy_manager.settings_store import load as load_settings
for name in ("start_engine", "stop_engine", "stop_overlay_host", "clear_live_session_markers", "ensure_running"):
    setattr(L, name, lambda *a, **k: None)
L.engine_health = lambda *a, **k: {"running": True}
L.ensure_overlay_host = lambda *a, **k: {"ok": True, "heartbeat": True, "detail": "host"}
L.detect_game = lambda *a, **k: True
state = {"mismatch": False}
L.elevation_mismatch = lambda: state["mismatch"]
relaunches = []
result = {"v": (False, "Administrator permission was not given, so Academy Engine was not restarted.")}
L.elevation.relaunch_elevated = lambda *a, **k: (relaunches.append(1), result["v"])[1]
win = L.Launcher(); win.timer.stop()
win.poll()
assert win.elev_row.isHidden(), "button shown without a mismatch"
state["mismatch"] = True; win.poll()
assert not win.elev_row.isHidden() and relaunches == [], "button missing, or restarted without being asked"
assert "Needs administrator" in win.overlay.text() and "administrator" in win.overlay_detail.text()
win.elev_btn.click()
assert relaunches == [1] and "permission was not given" in win.overlay_detail.text()
assert not win.elev_row.isHidden()                                # still offered after a refusal
win.elev_auto.setChecked(True)
assert load_settings().get("auto_elevate") is True
win2 = L.Launcher(); win2.timer.stop()
assert win2.elev_auto.isChecked()
win2.poll(); win2.poll()
assert relaunches == [1, 1], "automatic restart must be tried once per session"
result["v"] = (True, "Restarting Academy Engine as administrator…")
win3 = L.Launcher(); win3.timer.stop()                            # first poll runs inside __init__: restart decided at start-up
assert relaunches == [1, 1, 1] and win3._restarting
run_src = (ROOT / "academy_manager/launcher.py").read_text(encoding="utf-8")
assert "if not w._restarting:" in run_src                         # run() never shows a launcher that is restarting
win3.show(); app.processEvents()                                  # once the event loop runs, the old launcher closes
assert relaunches == [1, 1, 1] and not win3.isVisible(), "a started restart must close this launcher"
state["mismatch"] = False; win.poll()
assert win.elev_row.isHidden()
print("Launcher: button only with a mismatch; 'always' restarts once per session; refusal keeps running; restart closes it: PASS")
print("FC27 Academy Engine v1.0.1 regression: PASS")
