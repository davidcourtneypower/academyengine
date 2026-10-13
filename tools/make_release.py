"""Build the public release zip from an allowlist (v1.24.38).

    python tools/make_release.py OUT_DIR [--name FC27_Academy_v1.24.38]

Only files the mod needs at run time go in: no tests, developer tools, internal docs,
debug symbols or Python caches. Files are taken from git (tracked files only), so local
leftovers never ship; outside a git checkout the files on disk are used. The developer zip (everything tracked) is built separately.
"""
from __future__ import annotations
import argparse, fnmatch, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INCLUDE = [
    "FC27 Academy Engine.bat", "RESET_ALL_ACADEMY_DATA.bat", "UNINSTALL.bat", "VERSION.txt",
    "requirements-gui.txt", "run_manager.py", "run_bridge_service.py",
    "fc27_academy/*", "academy_manager/*", "integration/lua/*", "assets/*", "data/*",
    "native_overlay/AcademyOverlayHost.exe", "native_overlay/README.txt",
    "native_overlay/source/*",          # shipped for transparency: what the overlay program does
]
EXCLUDE = ["*/__pycache__/*", "*.pyc", "*.pdb", "*.syso"]   # .syso: generated build input (from the .rc)
TOP_LEVEL = {"release/README.txt": "README.txt", "release/THIRD_PARTY_NOTICES.txt": "THIRD_PARTY_NOTICES.txt"}   # player files at the top
REQUIRED = ["release/README.txt", "release/THIRD_PARTY_NOTICES.txt", "UNINSTALL.bat", "academy_manager/uninstall.py", "FC27 Academy Engine.bat", "run_manager.py", "run_bridge_service.py", "VERSION.txt",
            "integration/lua/FC27_Academy_Engine_Runtime.lua", "integration/lua/FC27_Academy_Engine_Autorun.lua",
            "native_overlay/AcademyOverlayHost.exe",
            "data/academy_settings.default.json"]


def tracked() -> list[str]:
    """Tracked files from git; outside a git checkout, every file on disk (the allowlist still decides)."""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [line for line in out.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        return [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()]


def release_files(files: list[str]) -> list[str]:
    keep = [f for f in files if (f in TOP_LEVEL or any(fnmatch.fnmatchcase(f, p) for p in INCLUDE))
            and not any(fnmatch.fnmatchcase(f, p) for p in EXCLUDE)]
    missing = [r for r in REQUIRED if r not in keep]
    if missing:
        raise SystemExit(f"release is missing required files: {missing}")
    return sorted(keep)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--name", default=None)
    ap.add_argument("--runtime", default=None, help="a prepared runtime folder (tools/build_windows_release.py) to include as runtime/")
    a = ap.parse_args()
    version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").split()[0].lstrip("v")
    name = a.name or f"FC27_Academy_Engine_v{version}"
    files = release_files(tracked())
    out = Path(a.out_dir) / f"{name}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(ROOT / f, f"FC27_Academy_Engine/{TOP_LEVEL.get(f, f)}")
        extra = 0
        if a.runtime:
            rt = Path(a.runtime)
            if not (rt / "python" / "pythonw.exe").exists():
                raise SystemExit(f"{rt} is not a prepared runtime (python/pythonw.exe missing)")
            records = [p.name for p in rt.rglob("*.dist-info")]
            if records:                                       # v1.0.5: they made VirusTotal call the zip a Python package
                raise SystemExit(f"{rt} still has package install records: {records}")
            for p in sorted(rt.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    z.write(p, "FC27_Academy_Engine/runtime/" + p.relative_to(rt).as_posix()); extra += 1
    print(f"{out}  ({len(files)} files{f' + {extra} runtime files' if extra else ''}, {out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
