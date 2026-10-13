"""v1.24.29 regressions: debug mode widens speeds/targets (and clamps back), OVR/POT
multi-range filters, 100-row pages, settings page (protected rules at top, sections),
overview/development wording."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["FC27AE_DEBUG"] = "1"   # v1.24.38: debug / stress-test mode is hidden by default
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12429_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fc27_academy import runtime_config as rc
from fc27_academy.settings import validate
cfg = rc.SETTINGS_PATH; cfg.parent.mkdir(parents=True, exist_ok=True)
def put(dev, prod):
    cfg.write_text(json.dumps({"development": dev, "production": prod})); rc.load_runtime_settings(force=True)
put({"playstyle_progression_speed": 50}, {"normal_playstyle_threshold": 20, "playstyle_plus_threshold": 15})
assert rc.normal_progress_multiplier() == 10.0 and rc.normal_threshold() == 50.0 and rc.plus_threshold() == 100.0
put({"playstyle_progression_speed": 50}, {"normal_playstyle_threshold": 20, "playstyle_plus_threshold": 15, "debug_stress_mode": True})
assert rc.normal_progress_multiplier() == 50.0 and rc.normal_threshold() == 20.0 and rc.plus_threshold() == 20.0   # PS+ never below normal
assert not validate({"development": {"role_progression_speed": 80}, "production": {"debug_stress_mode": True, "normal_playstyle_threshold": 10}})
assert validate({"development": {"role_progression_speed": 80}, "production": {"normal_playstyle_threshold": 10}})
from academy_manager import overlay_export as ex
data = {"development": {"playstyle_progression_speed": 50, "role_progression_speed": 0.5},
        "production": {"debug_stress_mode": True, "normal_playstyle_threshold": 20, "playstyle_plus_threshold": 30, "max_total_changes_per_checkpoint": 300}}
assert ex._clamp_to_normal_ranges(data)
assert data["development"]["playstyle_progression_speed"] == 10.0 and data["development"]["role_progression_speed"] == 0.5
assert data["production"]["normal_playstyle_threshold"] == 50.0 and data["production"]["playstyle_plus_threshold"] == 100.0
assert data["production"]["max_total_changes_per_checkpoint"] == 64
put({}, {})
print("Debug mode: speeds up to 100x and targets down to 10; turning it off clamps back to normal ranges: PASS")

from academy_manager import read_model as rm
rows = [dict(playerid=i, name=f"P{i}", club="X", ovr=o, potential=p) for i, (o, p) in enumerate([(55, 62), (61, 75), (67, 82), (72, 88), (81, 91)], 1)]
rm.sync_world("K", {}, rows)
q = lambda **f: sorted(r["playerid"] for r in rm.query_players(dict(storage_key="K", **f), limit=100)[0])
assert q(ovr_ranges="60-64,65-69") == [2, 3]
assert q(ovr_ranges="80+") == [5] and q(pot_ranges="85-89,90+") == [4, 5]
assert q(ovr_ranges="Any OVR") == [1, 2, 3, 4, 5]
assert q(ovr_ranges="60-64,80+", pot_ranges="90+") == [5]
assert q(ovr_min=70) == [4, 5]                                         # legacy saved views still work
assert ex.DEFAULT_VIEW["limit"] == 100 and ex.PAGE_LIMIT_MAX == 1000
print("Filters: OVR / POT multi-range selection in the query; 100-row pages up to 1000: PASS")

src = (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
assert "PROTECTED_RULES=" in src and "'safety'" not in src.split("group_order=")[1].split("\n")[0]
assert "'appearance','Dark','','Choose" in src and "'appearance','F8','','Keyboard" in src and "'appearance','On','On'," in src
c_src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
for needle in ('"NO PENDING CHANGES"', '" UNSAVED CHANGE"', 'head(dc,"CURRENT PLAYSTYLES",52,y+12,280,24,C_INFO', '" PlayStyles");',
               '"PLAYSTYLE PATHS"', 'small(dc,"Not eligible",x+18,yy,w-36,24,C_BAD', '"^  Back to top"', 'reset_button(dc,"RESET FILTERS",xs[10],g_fy[10],ws[10],1)',
               'small(dc,p->status,52,y+44'):
    assert needle in c_src, needle
assert '"Load 80 more"' not in c_src and '"STANDARD PLAYSTYLE PATHS"' not in c_src and "lane_chips(dc,p->status" not in c_src
print("Settings: protected rules at the top, no 'recommended' for theme/hotkey, On/Off default, uppercase status; overview/development wording: PASS")

cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Native harness: SKIPPED"); sys.exit(0)
t = Path(tempfile.mkdtemp())
c = c_src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
(t / "overlay_llp64.c").write_text(c, encoding="utf-8"); shutil.copy(ROOT / "tests/native/settings_ui_v12429_harness.c", t / "harness.c")
flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
first = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c")], capture_output=True, text=True)
missing = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
(t / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in missing))
r = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c"), str(t / "stubs.c")], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-3000:]
out = subprocess.run([str(t / "h")], capture_output=True, text=True); print(out.stdout.strip())
assert out.returncode == 0 and "PASS" in out.stdout
print("FC27 Academy Engine v1.24.29 regression: PASS")
