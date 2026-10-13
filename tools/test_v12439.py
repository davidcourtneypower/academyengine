"""v1.24.39 regressions: release candidate packaging.

1. PE import reader (used to trim Qt) reads our own overlay binaries correctly.
2. Qt trim keeps the import closure of the roots and removes everything else.
3. Windows runtime build: embeddable-zip checks, sys.path file, locked wheels (full build only
   when the locked wheels are available offline via FC27AE_WHEELS; otherwise SKIPPED).
4. Release zip: player README and notices at the top, uninstaller included, runtime/ included
   when given, developer README left out.
5. Launcher prefers the bundled Python; requirements pinned.
6. Uninstaller removes only Academy Engine's autorun files, the faces it wrote, and the
   engine data only when asked.
"""
from __future__ import annotations
import io, json, os, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12439_")
import build_windows_release as B

# ---- 1. PE imports ---------------------------------------------------------------------------------
dll = ROOT / "native_overlay/AcademyOverlayHost.exe"     # v1.0.6: the overlay is one program (no DLL); any of our PE files will do
imp = B.pe_imports(dll)
assert {"kernel32.dll", "user32.dll", "gdi32.dll"} <= imp, imp
assert B.pe_imports(ROOT / "README.md") == set()
print("PE import reader: overlay program imports read; non-PE files ignored: PASS")

# ---- 2. Qt trim (synthetic tree built from our own PE files) -----------------------------------------
t = Path(tempfile.mkdtemp()) / "PySide6"
for rel in B.QT_ROOTS:
    (t / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy(dll, t / rel)   # each imports user32.dll etc.
shutil.copy(dll, t / "user32.dll")                     # a local DLL in the closure: must stay
shutil.copy(dll, t / "Qt6Quick.dll")                   # not reached: must go
(t / "plugins/qmltooling").mkdir(parents=True); shutil.copy(dll, t / "plugins/qmltooling/qmldbg.dll")
(t / "qml/QtQuick").mkdir(parents=True); (t / "qml/QtQuick/x.qml").write_text("x")
(t / "translations").mkdir(); (t / "translations/qt_de.qm").write_text("x")
(t / "designer.exe").write_text("x"); (t / "QtCore.pyi").write_text("x"); (t / "pyside6.abi3.lib").write_text("x")
(t / "__init__.py").write_text("# keep"); (t / "support").mkdir(); (t / "support/__init__.py").write_text("")
removed, size = B.trim_qt(t)
left = sorted(p.relative_to(t).as_posix() for p in t.rglob("*") if p.is_file())
for keep in B.QT_ROOTS + ["user32.dll", "__init__.py", "support/__init__.py"]:
    assert keep in left, keep
for gone in ("Qt6Quick.dll", "plugins/qmltooling/qmldbg.dll", "qml/QtQuick/x.qml", "translations/qt_de.qm", "designer.exe", "QtCore.pyi", "pyside6.abi3.lib"):
    assert gone not in left, gone
assert not (t / "qml").exists() and not (t / "plugins/qmltooling").exists()
print("Qt trim: import closure of QtCore/QtGui/QtWidgets and the needed plugins kept; QML, tools, translations removed: PASS")

# ---- 3. runtime build ---------------------------------------------------------------------------------
def stub_zip(files) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for f in files:
            z.writestr(f, "#import site\n" if f.endswith("._pth") else "stub")
    return b.getvalue()
good = ["python.exe", "pythonw.exe", "python312.dll", "python312._pth", "python312.zip", "LICENSE.txt"]
bad = Path(tempfile.mkdtemp()) / "rt"
try:
    B.build_runtime(bad, stub_zip([f for f in good if f != "pythonw.exe"])); raise AssertionError("accepted a zip without pythonw.exe")
except SystemExit as e:
    assert "pythonw.exe" in str(e)
import hashlib as _h
blob = stub_zip(good); zp = Path(tempfile.mkdtemp()) / "py.zip"; zp.write_bytes(blob)
try:
    B.get_python_zip(str(zp), Path(tempfile.mkdtemp()), None); raise AssertionError("accepted a Python zip with the wrong hash")
except SystemExit as e:
    assert "does not match" in str(e)
assert B.get_python_zip(str(zp), Path(tempfile.mkdtemp()), _h.sha256(blob).hexdigest()) == blob
assert B.PY_SHA256 == "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
assert "Upload this file to Nexus Mods" in (ROOT / "tools/build_windows_release.py").read_text()
lock = (ROOT / "tools/requirements-windows.lock").read_text()
assert all(n in lock for n in ("pyside6-essentials==", "shiboken6==", "psutil==", "pillow==")) and lock.count("--hash=sha256:") == 4
wheels = os.environ.get("FC27AE_WHEELS")
if wheels and Path(wheels).is_dir():
    rt = Path(tempfile.mkdtemp()) / "runtime"
    B.build_runtime(rt, stub_zip(good))
    pth = (rt / "python/python312._pth").read_text()
    assert pth.splitlines() == ["python312.zip", ".", "Lib\\site-packages", "..\\..", "import site"], pth
    site = rt / "python/Lib/site-packages"
    for need in ("PySide6/QtWidgets.pyd", "PySide6/Qt6Widgets.dll", "PySide6/plugins/platforms/qwindows.dll", "PySide6/plugins/imageformats/qsvg.dll",
                 "shiboken6", "psutil", "PIL"):
        assert (site / need).exists(), need
    assert not (site / "PySide6/qml").exists() and not list(site.rglob("__pycache__"))
    print(f"Runtime: stub embeddable zip + locked wheels -> {sum(f.stat().st_size for f in rt.rglob('*') if f.is_file()) / 1e6:.0f} MB, sys.path file correct: PASS")
else:
    rt = Path(tempfile.mkdtemp()) / "runtime"
    (rt / "python").mkdir(parents=True)
    for f in good: (rt / "python" / f).write_text("stub")
    print("Runtime: embeddable-zip checks and lock file PASS; full wheel build SKIPPED (set FC27AE_WHEELS to a folder of the locked wheels)")

# ---- 4. release zip ------------------------------------------------------------------------------------
out = Path(tempfile.mkdtemp())
r = subprocess.run([sys.executable, str(ROOT / "tools/make_release.py"), str(out), "--name", "w", "--runtime", str(rt)], capture_output=True, text=True, cwd=ROOT)
assert r.returncode == 0, r.stdout + r.stderr
names = [n.split("/", 1)[1] for n in zipfile.ZipFile(out / "w.zip").namelist()]
for need in ("README.txt", "THIRD_PARTY_NOTICES.txt", "UNINSTALL.bat", "academy_manager/uninstall.py", "runtime/python/pythonw.exe", "FC27 Academy Engine.bat"):
    assert need in names, need
assert "README.md" not in names and "release/README.txt" not in names
readme = zipfile.ZipFile(out / "w.zip").read("FC27_Academy_Engine/README.txt").decode()
for must in ("REQUIREMENTS", "INSTALL", "UNINSTALL", "Borderless", "Total Career Overhaul", "%LOCALAPPDATA%\\FC27AcademyEngine"):
    assert must in readme, must
r = subprocess.run([sys.executable, str(ROOT / "tools/make_release.py"), str(out), "--name", "x", "--runtime", str(out)], capture_output=True, text=True, cwd=ROOT)
assert r.returncode != 0 and "not a prepared runtime" in (r.stdout + r.stderr)
print("Release zip: README.txt and notices at the top, uninstaller, runtime/ included; no developer README; bad runtime refused: PASS")

# ---- 5. launcher and pins ---------------------------------------------------------------------------------
bat = (ROOT / "FC27 Academy Engine.bat").read_bytes().decode("ascii")
assert "\r\n" in bat and bat.index("runtime\\python\\pythonw.exe") < bat.index("pip install")
un = (ROOT / "UNINSTALL.bat").read_bytes().decode("ascii")
assert "runtime\\python\\python.exe" in un and "uninstall.py" in un
req = (ROOT / "requirements-gui.txt").read_text().split()
assert req and all("==" in x for x in req), req
print("Launcher: bundled Python first, installed Python as fallback; requirements pinned: PASS")

# ---- 6. uninstaller ------------------------------------------------------------------------------------------
from academy_manager import uninstall as U
from academy_manager.settings_store import save as save_settings
from fc27_academy.paths import USER_ROOT
le = Path(tempfile.mkdtemp()) / "FC 27 Live Editor"
(le / "lua/autorun").mkdir(parents=True); (le / "le_config.json").write_text("{}")
ours = le / "lua/autorun/FC27_Academy_Engine.lua"
shutil.copy(ROOT / "integration/lua/FC27_Academy_Engine_Autorun.lua", ours)
other = le / "lua/autorun/SomeOtherMod.lua"; other.write_text("-- not ours")
le2 = Path(tempfile.mkdtemp()) / "LE2"; (le2 / "lua/autorun").mkdir(parents=True)
foreign = le2 / "lua/autorun/FC27_Academy_Engine.lua"; foreign.write_text("-- someone else's file with our name")
USER_ROOT.mkdir(parents=True, exist_ok=True)
save_settings({"live_editor_data_root": str(le)})
cands = U.autorun_candidates()
assert ours in cands, cands
removed, skipped = U.remove_autoruns(cands + [foreign])
assert not ours.exists() and other.exists() and foreign.exists(), (removed, skipped)
assert any("not Academy Engine's file" in s for s in skipped)
from fc27_academy import face_ingame
mfile = le / "mods/legacy/data/ui/imgAssets/heads/p460001.dds"; mfile.parent.mkdir(parents=True); mfile.write_bytes(b"ours")
mine = le / "mods/legacy/data/ui/imgAssets/heads/p460002.dds"; mine.write_bytes(b"user's own")
import hashlib
face_ingame.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
face_ingame.MANIFEST.write_text(json.dumps({"files": {str(mfile): {"sha": hashlib.sha256(b"ours").hexdigest(), "src": "x.png"}}}))
res = U.remove_written_faces()
assert res.get("removed") == 1 and not mfile.exists() and mine.exists(), res
assert U.main(["--keep-data"]) == 0 and USER_ROOT.exists()
assert U.main(["--delete-data"]) == 0 and not USER_ROOT.exists()
print("Uninstaller: only Academy Engine's autorun files and written faces removed; data kept or deleted as asked: PASS")
print("FC27 Academy Engine v1.24.39 regression: PASS")
