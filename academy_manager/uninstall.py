"""Uninstall Academy Engine from Live Editor (v1.24.39). Run by UNINSTALL.bat.

1. Removes the autorun file (lua/autorun/FC27_Academy_Engine.lua) from every Live Editor
   folder the launcher may have used, but only files that are Academy Engine's bootstrap.
2. Removes any minifaces the experimental face writer put in Live Editor's folders (only
   files it wrote and that are unchanged; your own minifaces are never touched).
3. Optionally deletes all engine data (%LOCALAPPDATA%\\FC27AcademyEngine).
The mod's own folder is left for you to delete. Your FC27 saves are never touched.
"""
from __future__ import annotations
import shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MARKER = b"FC27 Academy Engine"
AUTORUN_NAME = "FC27_Academy_Engine.lua"


def autorun_candidates() -> list[Path]:
    from academy_manager.settings_store import load as load_settings
    from academy_manager.live_editor_integration import all_live_editor_data_roots, discover_live_editor_root
    s = {}
    try:
        s = load_settings() or {}
    except Exception:
        pass
    roots: list[Path] = []
    try:
        binary = discover_live_editor_root(s.get("live_editor_root") or None)
    except Exception:
        binary = None
    try:
        roots += [Path(r) for r in all_live_editor_data_roots(s.get("live_editor_data_root") or None, binary_root=binary)]
    except Exception:
        pass
    for key in ("live_editor_data_root", "live_editor_root"):
        if s.get(key):
            roots.append(Path(s[key]))
    seen, out = set(), []
    for r in roots:
        f = r / "lua" / "autorun" / AUTORUN_NAME
        k = str(f).lower()
        if k not in seen:
            seen.add(k); out.append(f)
    return out


def remove_autoruns(files: list[Path]) -> tuple[list[str], list[str]]:
    removed, skipped = [], []
    for f in files:
        try:
            if not f.is_file():
                continue
            if MARKER not in f.read_bytes()[:400]:
                skipped.append(f"{f} (not Academy Engine's file, left alone)"); continue
            f.unlink(); removed.append(str(f))
        except OSError as exc:
            skipped.append(f"{f} ({exc})")
    return removed, skipped


def remove_written_faces() -> dict:
    try:
        from fc27_academy import face_ingame
        if not face_ingame.MANIFEST.exists():
            return {"removed": 0}
        return face_ingame.sync({"players": {}}, None, [], enabled=False)
    except Exception as exc:
        return {"removed": 0, "error": str(exc)}


def delete_engine_data() -> bool:
    from fc27_academy.paths import USER_ROOT
    if USER_ROOT.exists():
        shutil.rmtree(USER_ROOT, ignore_errors=True)
    return not USER_ROOT.exists()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    yes_data = "--delete-data" in argv
    keep_data = "--keep-data" in argv
    print("FC27 Academy Engine - Uninstall\n")
    print("Close FC27, FC Live Editor and the Academy Engine launcher first.\n")
    removed, skipped = remove_autoruns(autorun_candidates())
    for r in removed:
        print(f"Removed Live Editor autorun: {r}")
    for s in skipped:
        print(f"Skipped: {s}")
    if not removed and not skipped:
        print("No Academy Engine autorun found in Live Editor (already removed).")
    faces = remove_written_faces()
    if faces.get("removed"):
        print(f"Removed {faces['removed']} minifaces Academy Engine had written to Live Editor.")
    if not keep_data and not yes_data:
        try:
            ans = input("\nAlso delete all Academy Engine data (development progress for every career)? Type DELETE to confirm, or press Enter to keep it: ")
        except EOFError:
            ans = ""
        yes_data = ans.strip().upper() == "DELETE"
    if yes_data:
        print("Engine data deleted." if delete_engine_data() else "Some engine data could not be deleted (is the launcher still open?).")
    else:
        print("Engine data kept. Reinstalling later picks your careers up again.")
    print("\nDone. You can now delete the Academy Engine folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
