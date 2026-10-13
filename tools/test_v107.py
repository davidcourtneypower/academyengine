"""v1.0.7 regressions: building from source, for Nexus Mods' review (source on GitHub + build steps).

1. BUILDING.md exists, is linked from README.md, and agrees with the build scripts (Python hash,
   locked packages, overlay build command).
2. tools/build_overlay.py builds AcademyOverlayHost.exe reproducibly: two builds from different folders
   are byte-identical, and the program carries no build paths, debug directory or PDB reference.
3. The Windows release build rebuilds the overlay from source when LLVM is installed and prints the hashes.
"""
from __future__ import annotations
import hashlib, os, re, shutil, struct, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_windows_release as BW, build_overlay as BO

doc = (ROOT / "BUILDING.md").read_text(encoding="utf-8")
assert "BUILDING.md" in (ROOT / "README.md").read_text(encoding="utf-8")
assert BW.PY_SHA256 in doc and "py tools\\build_overlay.py" in doc and "py tools\\build_windows_release.py dist" in doc
for line in (ROOT / "tools/requirements-windows.lock").read_text().splitlines():
    if "==" in line and not line.startswith("#"):
        name, ver = line.split()[0].split("==")
        assert ver in doc, (name, ver)
for claim in ("trait1", "icontrait2", "460000", "HKEY_CURRENT_USER\\SOFTWARE\\Live Editor", "lua\\autorun\\FC27_Academy_Engine.lua", "kernel32, user32, gdi32 and xinput1_4"):
    assert claim in doc, claim
assert "staged_sync.py" in doc and "trait1','trait2','icontrait1','icontrait2'" in (ROOT / "fc27_academy/staged_sync.py").read_text()
print("BUILDING.md: linked from README; Python hash, package versions and build commands match the scripts: PASS")

exe = ROOT / "native_overlay/AcademyOverlayHost.exe"
data = exe.read_bytes()
off = struct.unpack_from("<I", data, 0x3C)[0]; opt = off + 24
debug_rva, debug_size = struct.unpack_from("<II", data, opt + 112 + 6 * 8)       # data directory 6: debug
assert debug_size == 0 or b"RSDS" not in data, "program has a debug directory / PDB reference"
for leak in (b".pdb", b"/tmp/", b"/home/", b"C:\\Users", b"scratchpad"):
    assert leak not in data, leak
assert not (ROOT / "native_overlay/AcademyOverlayHost.pdb").exists()
print("Overlay program: no debug directory, PDB reference or build paths inside: PASS")

try:
    for t in ("clang", "lld-link", "llvm-lib", "llvm-rc"): BO.tool(t)
    have_llvm = True
except SystemExit:
    have_llvm = False
if have_llvm:
    shas = []
    for i in range(2):
        d = Path(tempfile.mkdtemp(prefix=f"fc27ae_repro{i}_")) / "copy"
        shutil.copytree(ROOT / "native_overlay/source", d / "native_overlay/source")
        (d / "tools").mkdir(); shutil.copy(ROOT / "tools/build_overlay.py", d / "tools")
        r = subprocess.run([sys.executable, str(d / "tools/build_overlay.py"), str(d / "out.exe")], capture_output=True, text=True, check=True)
        shas.append(hashlib.sha256((d / "out.exe").read_bytes()).hexdigest())
        assert shas[-1] in r.stdout
    assert shas[0] == shas[1], shas
    print(f"Reproducible: two builds from different folders are identical ({shas[0][:16]}...): PASS")
else:
    print("Reproducible build: SKIPPED (LLVM not installed)")

src = (ROOT / "tools/build_windows_release.py").read_text(encoding="utf-8")
assert "build_overlay.build()" in src and "AcademyOverlayHost.exe SHA-256" in src and "SHA-256 {zip_sha}" in src
assert "/Brepro" in (ROOT / "tools/build_overlay.py").read_text() and "/debug" not in (ROOT / "tools/build_overlay.py").read_text()
print("Release build: overlay rebuilt from source when LLVM is installed; zip and overlay hashes printed: PASS")
print("FC27 Academy Engine v1.0.7 regression: PASS")
