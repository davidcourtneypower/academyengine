"""v1.24.22 regressions: settings belong to the career (never roll back with a branch),
negative setting values in the overlay, NEXT PS header."""
import json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12422_")

from fc27_academy import runtime_config as rc
from fc27_academy.save_context import inherit_settings
from fc27_academy.paths import ACADEMY_STATE_ROOT

# ---- settings are per career --------------------------------------------------------------
a, b = "SAVE1__branch__A", "SAVE1__branch__B"
assert rc.career_settings_path(a) == rc.career_settings_path(b) == rc._CAREER_SETTINGS_ROOT / "SAVE1.json"
assert rc.career_settings_path("SAVE2__branch__A") != rc.career_settings_path(a)
root = rc._CAREER_SETTINGS_ROOT; root.mkdir(parents=True, exist_ok=True)
# migration: newest per-branch file seeds the career file
(root / "SAVE3__branch__old.json").write_text(json.dumps({"development": {"playstyle_progression_speed": 1.0}}))
time.sleep(0.02)
(root / "SAVE3__branch__new.json").write_text(json.dumps({"development": {"playstyle_progression_speed": 3.0}}))
p = rc.career_settings_path("SAVE3__branch__old")
assert json.loads(p.read_text())["development"]["playstyle_progression_speed"] == 3.0
# a change made on one branch is what every other branch of the career sees
p.write_text(json.dumps({"development": {"playstyle_plus_eligibility_multiplier": 3.0}}))
assert inherit_settings(ACADEMY_STATE_ROOT, "SAVE3__branch__new", "SAVE3__branch__rewind") is False
assert json.loads(rc.career_settings_path("SAVE3__branch__rewind").read_text())["development"]["playstyle_plus_eligibility_multiplier"] == 3.0
# another career (Save As to a new slot) inherits a copy once, never overwriting its own
assert inherit_settings(ACADEMY_STATE_ROOT, "SAVE3__branch__new", "SAVE4__branch__x") is True
assert json.loads(rc.career_settings_path("SAVE4__branch__x").read_text())["development"]["playstyle_plus_eligibility_multiplier"] == 3.0
rc.career_settings_path("SAVE4__branch__x").write_text(json.dumps({"development": {}}))
assert inherit_settings(ACADEMY_STATE_ROOT, "SAVE3__branch__new", "SAVE4__branch__y") is False
print("Settings: one file per career shared by every branch (rewind/reload never restores older settings); newest legacy branch file migrated; Save As inherits once: PASS")

# ---- definitions / defaults -------------------------------------------------------------------
from academy_manager.setting_definitions import SETTINGS
keys = {s["key"] for s in SETTINGS}
assert not keys & {"newgen_starting_playstyles_offset", "lifetime_playstyle_cap_offset"}   # removed in v1.24.23
c_src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert '"NEXT PS","PS PROGRESS"' in c_src and "stay even if you quit without saving the career" in c_src
print("Settings page note; NEXT PS header; v1.24.22 generation settings removed again: PASS")

cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Native settings harness: SKIPPED"); sys.exit(0)
t = Path(tempfile.mkdtemp())
c = c_src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
(t / "overlay_llp64.c").write_text(c, encoding="utf-8"); shutil.copy(ROOT / "tests/native/settings_v12422_harness.c", t / "harness.c")
flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
first = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c")], capture_output=True, text=True)
missing = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
(t / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in missing))
r = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c"), str(t / "stubs.c")], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-3000:]
out = subprocess.run([str(t / "h")], capture_output=True, text=True); print(out.stdout.strip())
assert out.returncode == 0 and "PASS" in out.stdout
print("FC27 Academy Engine v1.24.22 regression: PASS")
