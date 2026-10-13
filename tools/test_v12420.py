"""v1.24.20 regressions: filters (status scope, wording, legacy views, multi-select popups
staged without their own apply), settings order."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12420_")

# ---- read-model filters -------------------------------------------------------------
from academy_manager import read_model as rm
rows = [
    dict(playerid=1, name="A", club="X", next_ps="Rapid", next_ps_pct=40, normal_count=2, cap=5, plus_eligible=False, lifecycle="CLUB", observed_this_checkpoint=True),
    dict(playerid=2, name="B", club="X", next_plus="Rapid", next_plus_pct=30, normal_count=3, cap=5, plus_eligible=True, lifecycle="CLUB", observed_this_checkpoint=True),
    dict(playerid=3, name="C", club="X", active_role_progress={"Playmaker": 50}, normal_count=1, cap=5, lifecycle="CLUB", observed_this_checkpoint=True),
    dict(playerid=4, name="D", club="X", normal_count=5, cap=5, lifecycle="CLUB", observed_this_checkpoint=True),
]
rm.sync_world("K", {}, rows)
def run(**f):
    return sorted(int(r["playerid"]) for r in rm.query_players(dict(storage_key="K", myclub=False, **f))[0])
assert run(state="Developing a PlayStyle") == [1]
assert run(state="Developing a PlayStyle+") == [2]
assert run(state="Developing a Role++") == [3]
assert run(state="At lifetime PlayStyle cap") == [4] and run(state="At lifetime cap") == [4]
assert run(plus_filter="PlayStyle+ eligible") == [2] and run(plus_filter="Eligible") == [2]
assert 2 not in run(plus_filter="Not PlayStyle+ eligible")
print("Filters: status covers PlayStyle / PlayStyle+ / Role++ development and the lifetime PlayStyle cap; new and legacy labels work: PASS")

# ---- legacy saved views ----------------------------------------------------------------
from academy_manager import overlay_export as ex
import json
ex.VIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
ex.VIEW_FILE.write_text(json.dumps({"storage_key": "K", "state": "At lifetime cap", "plus_filter": "Any PS+ Status"}))
v = ex._load_view("K")
assert v["state"] == "At lifetime PlayStyle cap" and v["plus_filter"] == "Any PlayStyle+ Status", v
print("Saved views from older builds migrate to the new labels: PASS")

# ---- settings order ---------------------------------------------------------------------
src = (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
assert "if x[0]!='debug']+(['faces'] if face_lib.faces_visible() else [])+['notifications','maintenance','appearance']+(['debug'] if debug_mode_available() else [])" in src   # v1.24.29: safety removed; v1.24.31 faces (hidden v1.24.37); v1.24.38 debug hidden
print("Settings: Debug / stress-test group is last: PASS")

# ---- native filter popups -----------------------------------------------------------------
cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Native filter harness: SKIPPED"); sys.exit(0)
t = Path(tempfile.mkdtemp())
c = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8").replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
(t / "overlay_llp64.c").write_text(c, encoding="utf-8"); shutil.copy(ROOT / "tests/native/filters_v12420_harness.c", t / "harness.c")
flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
first = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c")], capture_output=True, text=True)
missing = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
(t / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in missing))
subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c"), str(t / "stubs.c")], check=True)
out = subprocess.run([str(t / "h")], capture_output=True, text=True); print(out.stdout.strip())
assert out.returncode == 0 and "PASS" in out.stdout
