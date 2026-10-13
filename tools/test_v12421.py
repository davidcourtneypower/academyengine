"""v1.24.21 regressions: PlayStyle names instead of icons (rows grow to fit), icon pipeline
removed, Health tab and processing toast removed, PS+ eligibility locked at adoption."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12421_")

c_src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
for gone in ("draw_icon", "IconRec", "g_processing_toast", "PROCESSING_TOAST", '"Health"', "static void health("):
    assert gone not in c_src, gone
assert c_src.count("LoadImageA(NULL") == 2 and "g_sel_face,IMAGE_BITMAP" in c_src and "LoadImageA(NULL,path,IMAGE_BITMAP" in c_src   # only the v1.24.31 face and v1.24.32 picker loaders
assert not (ROOT / "academy_manager/local_icons.py").exists() and not (ROOT / "tools/download_playstyle_icons.py").exists()
assert not (ROOT / "assets/playstyles").exists()
ex_src = (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
assert "ICONS_BEGIN" not in ex_src and "PROCESSING_TOAST" not in ex_src and "processing_indicator" not in ex_src
import json
assert "processing_indicator" not in json.loads((ROOT / "data/academy_settings.default.json").read_text())["notifications"]
print("Icon download/render pipeline, processing toast and Health tab removed: PASS")

from academy_manager import overlay_export
assert "processing_indicator" not in {d.get("key") for d in overlay_export.SETTINGS_DEFS} if hasattr(overlay_export, "SETTINGS_DEFS") else True
print("Exporter imports without the icon module: PASS")

from fc27_academy import runtime_config
from fc27_academy.playstyle_lifetime import ensure_policy
cfg = runtime_config.SETTINGS_PATH; cfg.parent.mkdir(parents=True, exist_ok=True)
def set_mult(m):
    cfg.write_text(json.dumps({"development": {"playstyle_plus_eligibility_multiplier": m}})); runtime_config.load_runtime_settings(force=True)
set_mult(1.0)
p = {"playerid": 1, "engine": {}, "game": {"overallrating": 80, "potential": 90, "birthdate": 1, "nationality": 1}}
first = ensure_policy(p)["plus_eligible"]
set_mult(0.0); assert ensure_policy(p)["plus_eligible"] == first
set_mult(5.0); assert ensure_policy(p)["plus_eligible"] == first
set_mult(1.0)
print("PS+ eligibility locked at adoption whatever the multiplier later becomes: PASS")

cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Native names/rows harness: SKIPPED"); sys.exit(0)
t = Path(tempfile.mkdtemp())
c = c_src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
(t / "overlay_llp64.c").write_text(c, encoding="utf-8"); shutil.copy(ROOT / "tests/native/names_rows_v12421_harness.c", t / "harness.c")
flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
first = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c")], capture_output=True, text=True)
missing = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
(t / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in missing))
r = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c"), str(t / "stubs.c")], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-3000:]
out = subprocess.run([str(t / "h")], capture_output=True, text=True); print(out.stdout.strip())
assert out.returncode == 0 and "PASS" in out.stdout
print("FC27 Academy Engine v1.24.21 regression: PASS")
