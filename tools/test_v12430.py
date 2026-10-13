"""v1.24.30 regressions: event history can no longer be cleared from anywhere; 'PlayStyle'
wording; Misc section; shared controller help text; launcher hint shown on load; grey bars."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12430_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ex_src = (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
c_src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert "'clear_events','Clear event history'" not in ex_src and '"Clear history"' not in c_src and "write_clear_events();" not in c_src
assert "clear_events_for_storage(storage)" not in ex_src
print("Event history: no clear option in Events, Settings or the command handler: PASS")

for f in ("academy_manager/overlay_export.py", "academy_manager/setting_definitions.py", "academy_manager/live_data.py", "native_overlay/source/academy_overlay.c"):
    t = (ROOT / f).read_text(encoding="utf-8")
    assert "Normal PlayStyle" not in t and "normal PlayStyle" not in t, f
assert '"Cooldowns  •  normal "' not in c_src
print("Wording: 'PlayStyle(s)' instead of 'normal PlayStyle(s)' across the overlay: PASS")

assert "group_meta['appearance']=('Misc'" in ex_src
from academy_manager.controller import controller_help_text
h = controller_help_text("VIEW+RB")
assert h.startswith("Hold VIEW+RB") and "LT/RT switch sub-views" in h and controller_help_text("L3+R3", False).startswith("Controller input is ignored")
assert "controller_help_text(normalize_combo(ctl_combo)" in ex_src
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from academy_manager import launcher as L
src = (ROOT / "academy_manager/launcher.py").read_text(encoding="utf-8")
assert "self._update_ctl_hint()   # v1.24.30" in src and "setMinimumWidth(200)" in src
print("Settings 'Misc' section; controller help identical in launcher and overlay, shown on launch; wider combo: PASS")

assert "p>=50?RGB(138,146,156)" in c_src and "box(dc,r->right-630,r->bottom-47,214,34" in c_src
print("Grey progress band; pending-changes box wide enough: PASS")
print("FC27 Academy Engine v1.24.30 regression: PASS")
