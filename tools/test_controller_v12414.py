"""v1.24.14: ring cursor while the pad drives the pointer, and LT/RT sub-view switching
(player details tabs, event filters). Builds the real overlay source natively."""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Controller v1.24.14 harness: SKIPPED (no C compiler)"); sys.exit(0)
d = Path(tempfile.mkdtemp())
src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
src = src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
(d / "overlay_llp64.c").write_text(src, encoding="utf-8")
shutil.copy(ROOT / "tests/native/controller_v12414_harness.c", d / "harness.c")
flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
first = subprocess.run([cc, *flags, "-o", str(d / "h"), str(d / "harness.c")], capture_output=True, text=True)
missing = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
(d / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in missing))
subprocess.run([cc, *flags, "-o", str(d / "h"), str(d / "harness.c"), str(d / "stubs.c")], check=True)
out = subprocess.run([str(d / "h")], capture_output=True, text=True)
print(out.stdout.strip())
assert out.returncode == 0 and "PASS" in out.stdout
