"""v1.0.5 regressions: antivirus false positives (Nexus Mods quarantine, VirusTotal 5/67).

1. The Windows build removes the bundled packages' install records (*.dist-info), which made
   VirusTotal identify the whole download as the "pillow" Python package, and keeps their licence
   texts (plus LGPL/GPL v3) in runtime/licenses. The release packager refuses a runtime that still has them.
2. The overlay program carries Windows file details and a manifest that asks for no extra rights
   (asInvoker). (v1.0.6 replaced the Go host + DLL with one program; see test_v106.)
"""
from __future__ import annotations
import os, shutil, struct, subprocess, sys, tempfile, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT))
import build_windows_release as BW
import make_release as MR

# ---- 1. package records ---------------------------------------------------------------------------
t = Path(tempfile.mkdtemp())
site = t / "runtime" / "python" / "Lib" / "site-packages"
for name, files in {"pillow-12.3.0.dist-info": ["METADATA", "WHEEL", "RECORD", "licenses/LICENSE", "sboms/x.json"],
                    "psutil-7.2.2.dist-info": ["METADATA", "WHEEL", "LICENSE"],
                    "pyside6_essentials-6.12.0.dist-info": ["WHEEL", "entry_points.txt", "licenses/LicenseRef-Qt-Commercial.txt"]}.items():
    for f in files:
        p = site / name / f; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(f"{name} {f}")
(site / "PIL").mkdir(); (site / "PIL" / "__init__.py").write_text("")
moved = BW.tidy_package_metadata(site, t / "runtime" / "licenses")
lic = t / "runtime" / "licenses"
assert not list(site.rglob("*.dist-info")) and not list(site.rglob("WHEEL")) and (site / "PIL" / "__init__.py").exists()
assert (lic / "pillow" / "LICENSE").exists() and (lic / "psutil" / "LICENSE").exists() and (lic / "pyside6_essentials" / "LicenseRef-Qt-Commercial.txt").exists()
assert "LESSER GENERAL PUBLIC LICENSE" in (lic / "LGPL-3.0.txt").read_text() and "GNU GENERAL PUBLIC LICENSE" in (lic / "GPL-3.0.txt").read_text()
assert moved == 5, moved
src = (ROOT / "tools/build_windows_release.py").read_text(encoding="utf-8")
assert "tidy_package_metadata(site, runtime / \"licenses\")" in src
notices = (ROOT / "release/THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
assert "runtime\\licenses" in notices and "dist-info" not in notices
print("Build: package install records removed, licence texts (with LGPL/GPL v3) kept in runtime\\licenses: PASS")

# the packager refuses a runtime that still has them
rt = t / "rt"; (rt / "python").mkdir(parents=True); (rt / "python" / "pythonw.exe").write_text("x")
(rt / "python" / "Lib" / "site-packages" / "pillow-12.3.0.dist-info").mkdir(parents=True)
r = subprocess.run([sys.executable, str(ROOT / "tools/make_release.py"), str(t / "out"), "--runtime", str(rt)], capture_output=True, text=True)
assert r.returncode != 0 and "package install records" in (r.stderr + r.stdout), r
shutil.rmtree(rt / "python" / "Lib")
r = subprocess.run([sys.executable, str(ROOT / "tools/make_release.py"), str(t / "out"), "--runtime", str(rt), "--name", "x"], capture_output=True, text=True)
assert r.returncode == 0, r.stderr
names = zipfile.ZipFile(t / "out" / "x.zip").namelist()
assert not any(n.endswith(".syso") or n.endswith(".pdb") or ".dist-info" in n for n in names)
assert "FC27_Academy_Engine/native_overlay/source/academy_overlay.c" in names and "FC27_Academy_Engine/native_overlay/source/academy_overlay.rc" in names
print("Release zip: refuses package records; ships the overlay source and resource script, no debug symbols: PASS")

# ---- 2. Windows file details, symbols, manifest ----------------------------------------------------
def pe_header(b: bytes):
    off = struct.unpack_from("<I", b, 0x3C)[0]
    assert b[off:off + 4] == b"PE\0\0"
    return struct.unpack_from("<HHIII", b, off + 4)        # machine, sections, time, symtab ptr, symbol count
b = (ROOT / "native_overlay/AcademyOverlayHost.exe").read_bytes()          # v1.0.6: the only overlay file
for key in ("FileDescription", "ProductName", "FC27 Academy Engine", "OriginalFilename", "AcademyOverlayHost.exe"):
    assert key.encode("utf-16-le") in b, key
assert pe_header(b)[0] == 0x8664
assert b'level="asInvoker"' in b and b"requireAdministrator" not in b
assert "-s -w" not in (ROOT / "docs/DEVELOPER_CONTEXT.md").read_text(encoding="utf-8")
print("Overlay program: Windows file details and a manifest that asks for no extra rights: PASS")

# ---- 3. real build (optional: needs the locked wheels offline and the Python zip) ---------------------
wheels, pyzip = os.environ.get("FC27AE_WHEELS"), os.environ.get("FC27AE_PYTHON_ZIP")
if wheels and pyzip:
    out = Path(tempfile.mkdtemp())
    import hashlib
    sha = hashlib.sha256(Path(pyzip).read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(ROOT / "tools/build_windows_release.py"), str(out), "--python-zip", pyzip, "--python-sha256", sha], check=True, capture_output=True)
    z = next(out.glob("*_Windows.zip"))
    names = zipfile.ZipFile(z).namelist()
    assert not any(".dist-info" in n or n.endswith("/WHEEL") for n in names)
    assert "FC27_Academy_Engine/runtime/licenses/LGPL-3.0.txt" in names and "FC27_Academy_Engine/runtime/licenses/pillow/LICENSE" in names
    print("Real Windows build: no package records in the zip, licences present: PASS")
else:
    print("Real Windows build: SKIPPED (set FC27AE_WHEELS and FC27AE_PYTHON_ZIP)")
print("FC27 Academy Engine v1.0.5 regression: PASS")
