"""Build the self-contained Windows release: the mod plus its own Python (v1.24.39).

    python tools/build_windows_release.py OUT_DIR [--python-zip python-3.12.10-embed-amd64.zip]

Players need nothing installed. The zip carries Python's official "embeddable" package for
Windows (python.exe / pythonw.exe signed by the Python Software Foundation) with the exact
package versions in tools/requirements-windows.lock, checked by hash.

Steps
1. Python: the embeddable zip from python.org (downloaded, or given with --python-zip).
2. Packages: pip installs the locked Windows wheels into runtime/python/Lib/site-packages.
   Runs with whatever Python you start this script with (any OS); it only unpacks wheels.
3. Qt is trimmed to what the launcher uses (QtCore, QtGui, QtWidgets, the Windows platform and
   style plugins, SVG/ICO/JPEG images). What stays is the import closure of those files, read
   from their DLL import tables, so nothing they load is removed.
4. Package install records (*.dist-info) are removed and their licence texts moved to
   runtime/licenses/<package>/ (v1.0.5). Nothing Academy Engine runs reads them, and with them in
   the zip VirusTotal identified the whole download as the "pillow" Python package.
5. tools/make_release.py builds the zip with runtime/ inside.

Run it on the release PC once per release. Re-running reuses the download in OUT_DIR/cache.
"""
from __future__ import annotations
import argparse, hashlib, io, os, shutil, struct, subprocess, sys, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_VERSION = "3.12.10"                  # last 3.12 release with Windows binaries
PY_TAG = "312"
PY_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
# SHA-256 of python-3.12.10-embed-amd64.zip, recorded from the first release build (2026-10-11).
# Verified 2026-10-11: the same file's MD5 is fe8ef205f2e9c3ba44d0cf9954e1abd3, as published on
# python.org's 3.12.10 release page. Every build must match.
PY_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
LOCK = ROOT / "tools" / "requirements-windows.lock"

QT_ROOTS = ["QtCore.pyd", "QtGui.pyd", "QtWidgets.pyd",
            "plugins/platforms/qwindows.dll", "plugins/styles/qmodernwindowsstyle.dll",
            "plugins/imageformats/qsvg.dll", "plugins/imageformats/qico.dll",
            "plugins/imageformats/qjpeg.dll", "plugins/iconengines/qsvgicon.dll"]
QT_DROP_DIRS = ["qml", "translations", "metatypes", "typesystems", "include", "glue", "resources",
                "scripts", "doc", "examples", "lib", "Qt/qml", "Qt/translations"]


# ---- PE import tables (no third-party module needed) -------------------------------------------
def pe_imports(path: Path) -> set[str]:
    """Names of the DLLs a PE file imports (normal and delay-load), lower case."""
    b = path.read_bytes()
    if b[:2] != b"MZ":
        return set()
    pe = struct.unpack_from("<I", b, 0x3C)[0]
    if b[pe:pe + 4] != b"PE\0\0":
        return set()
    nsec = struct.unpack_from("<H", b, pe + 6)[0]
    opt_size = struct.unpack_from("<H", b, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", b, opt)[0]
    dd = opt + (112 if magic == 0x20B else 96)
    secs = []
    so = opt + opt_size
    for i in range(nsec):
        va, vsize, rawptr = (struct.unpack_from("<I", b, so + 40 * i + 12)[0], struct.unpack_from("<I", b, so + 40 * i + 8)[0],
                             struct.unpack_from("<I", b, so + 40 * i + 20)[0])
        rawsize = struct.unpack_from("<I", b, so + 40 * i + 16)[0]
        secs.append((va, max(vsize, rawsize), rawptr))

    def off(rva):
        for va, size, raw in secs:
            if va <= rva < va + size:
                return rva - va + raw
        return None

    def cstr(rva):
        o = off(rva)
        if o is None:
            return ""
        e = b.index(b"\0", o)
        return b[o:e].decode("ascii", "replace")

    names = set()
    for idx, entry, name_at in ((1, 20, 12), (13, 32, 4)):        # import table, delay-import table
        rva = struct.unpack_from("<I", b, dd + 8 * idx)[0]
        o = off(rva) if rva else None
        while o is not None and o + entry <= len(b):
            name_rva = struct.unpack_from("<I", b, o + name_at)[0]
            if not name_rva:
                break
            names.add(cstr(name_rva).lower())
            o += entry
    return names


def trim_qt(pyside: Path) -> tuple[int, int]:
    """Remove the Qt parts the launcher never loads. Returns (files removed, bytes removed)."""
    local = {p.name.lower(): p for p in pyside.glob("*") if p.suffix.lower() in (".dll", ".pyd")}
    keep: set[Path] = set()
    todo = [pyside / r for r in QT_ROOTS]
    missing = [str(p.relative_to(pyside)) for p in todo if not p.exists()]
    if missing:
        raise SystemExit(f"PySide6 is missing expected files: {missing}")
    while todo:
        p = todo.pop()
        if p in keep:
            continue
        keep.add(p)
        for dep in pe_imports(p):
            if dep in local and local[dep] not in keep:
                todo.append(local[dep])
    removed = size = 0
    for d in QT_DROP_DIRS:
        t = pyside / d
        if t.is_dir():
            for f in t.rglob("*"):
                if f.is_file():
                    removed += 1; size += f.stat().st_size
            shutil.rmtree(t)
    for f in list(pyside.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(pyside)
        drop = False
        if f.suffix.lower() in (".dll", ".pyd") and f not in keep:
            drop = True
        if f.suffix.lower() in (".exe", ".lib") or f.suffix == ".pyi":
            drop = True
        if rel.parts[0] == "plugins" and f not in keep:
            drop = True
        if drop:
            removed += 1; size += f.stat().st_size
            f.unlink()
    for d in sorted((p for p in pyside.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
        if not any(d.iterdir()):
            d.rmdir()
    return removed, size


# ---- build steps ---------------------------------------------------------------------------------
def get_python_zip(path: str | None, cache: Path, sha256: str | None) -> bytes:
    if path:
        data = Path(path).read_bytes()
    else:
        cache.mkdir(parents=True, exist_ok=True)
        cached = cache / Path(PY_URL).name
        if not cached.exists():
            print(f"downloading {PY_URL}")
            with urllib.request.urlopen(PY_URL, timeout=120) as r:
                cached.write_bytes(r.read())
        data = cached.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f"python embeddable zip sha256 {digest}")
    want = (sha256 or PY_SHA256).lower()
    if digest.lower() != want:
        raise SystemExit(f"python zip SHA-256 {digest} does not match the expected {want}. "
                         "Delete OUT_DIR/cache and download again; do not use this file.")
    return data


def build_runtime(runtime: Path, py_zip: bytes) -> None:
    if runtime.exists():
        shutil.rmtree(runtime)
    py = runtime / "python"
    py.mkdir(parents=True)
    zipfile.ZipFile(io.BytesIO(py_zip)).extractall(py)
    for need in ("python.exe", "pythonw.exe", f"python{PY_TAG}.dll", f"python{PY_TAG}._pth"):
        if not (py / need).exists():
            raise SystemExit(f"not a Python {PY_VERSION} embeddable zip: {need} missing")
    # sys.path: the standard library, site-packages and the mod's own folder (runtime/python -> ../..)
    (py / f"python{PY_TAG}._pth").write_text(f"python{PY_TAG}.zip\n.\nLib\\site-packages\n..\\..\nimport site\n", encoding="ascii")
    site = py / "Lib" / "site-packages"
    site.mkdir(parents=True)
    cmd = [sys.executable, "-m", "pip", "install", "--no-deps", "--require-hashes", "-r", str(LOCK),
           "--target", str(site), "--platform", "win_amd64", "--python-version", PY_VERSION[:4],
           "--implementation", "cp", "--only-binary=:all:", "--no-compile", "--disable-pip-version-check"]
    if os.environ.get("FC27AE_WHEELS"):                      # offline: a folder of the locked wheels
        cmd += ["--no-index", "--find-links", os.environ["FC27AE_WHEELS"]]
    subprocess.run(cmd, check=True)
    removed, size = trim_qt(site / "PySide6")
    print(f"Qt trimmed: {removed} files, {size / 1e6:.0f} MB removed")
    for d in list(site.glob("bin")):
        shutil.rmtree(d)
    for c in list(site.rglob("__pycache__")):
        shutil.rmtree(c)
    moved = tidy_package_metadata(site, runtime / "licenses")
    print(f"Package records removed; {moved} licence files kept in runtime\\licenses")


LICENCE_NAMES = ("licen", "copying", "notice", "authors")


def tidy_package_metadata(site: Path, licenses: Path) -> int:
    """Move each package's licence texts to licenses/<package>/ and delete its *.dist-info folder.

    The folders only record how pip installed the package. The engine never reads them (checked:
    only PySide6's developer deploy scripts do, and those are not shipped). The licence texts are
    kept, together with the LGPL/GPL texts PySide6's wheel does not carry (release/licenses).
    """
    licenses.mkdir(parents=True, exist_ok=True)
    moved = 0
    for info in sorted(site.glob("*.dist-info")):
        name = info.name.split("-")[0]
        for f in sorted(info.rglob("*")):
            if f.is_file() and any(k in f.name.lower() for k in LICENCE_NAMES):
                dest = licenses / name / f.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest); moved += 1
        shutil.rmtree(info)
    for f in sorted((ROOT / "release" / "licenses").glob("*.txt")):
        shutil.copy2(f, licenses / f.name); moved += 1
    left = [str(p) for p in site.rglob("*.dist-info")] + [str(p) for p in site.rglob("WHEEL")]
    if left:
        raise SystemExit(f"package records left behind: {left}")
    return moved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--python-zip")
    ap.add_argument("--python-sha256", help=f"expected SHA-256 (default: the recorded {PY_VERSION} hash)")
    a = ap.parse_args()
    out = Path(a.out_dir).resolve()
    runtime = out / "runtime"
    build_runtime(runtime, get_python_zip(a.python_zip, out / "cache", a.python_sha256))
    total = sum(f.stat().st_size for f in runtime.rglob("*") if f.is_file())
    print(f"runtime ready: {total / 1e6:.0f} MB")
    version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").split()[0].lstrip("v")
    name = f"FC27_Academy_Engine_v{version}_Windows"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_release.py"), str(out),
                    "--name", name, "--runtime", str(runtime)], check=True)
    print("\n" + "=" * 72)
    print("Upload this file to Nexus Mods (the player download):")
    print(f"  {out / (name + '.zip')}")
    print("Everything else in this folder (docs, tests, tools) is the developer project; do not upload it.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
