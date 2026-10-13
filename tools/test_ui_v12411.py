"""v1.24.11 regression: free-form local PlayStyle artwork, launcher guards, overlay source checks."""
from __future__ import annotations
import os, sys, tempfile, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12411_ui_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Single-instance guard never blocks startup off Windows; the module still compiles.
src = (ROOT / "run_manager.py").read_text()
ns = {}; exec(compile(src.split("if _already_running():")[0], "run_manager", "exec"), ns)
assert ns["_already_running"]() is False
import py_compile; py_compile.compile(str(ROOT / "academy_manager/launcher.py"), doraise=True)
from academy_manager.bridge import elevation_mismatch
assert elevation_mismatch() is False
print("Launcher: single-instance guard and elevation check are safe no-ops off Windows; launcher compiles: PASS")

# Overlay source: dashboard card rows no longer overlap; toasts cleared when no career is loaded.
c = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
m = re.search(r"title\(dc,n,x\+18,y\+(\d+),w-36,(\d+),.*?small\(dc,sub,x\+18,y\+(\d+),w-36,(\d+),.*?bar_compact\(dc,x\+18,y\+h-(\d+)", c)
ty, th, sy, sh, bo = map(int, m.groups()); h = 110
assert ty + th <= sy and sy + sh <= h - bo and h - bo + 10 <= h, (ty, th, sy, sh, bo)
assert "if(!g_loaded){g_event_toast_ticks=0;" in c
print("Overlay: metric card value/subtitle/bar stack without overlap; toasts cleared when career not loaded: PASS")
