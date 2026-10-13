# Developer context — FC27 Academy Engine

Orientation for anyone (or any AI session) picking up the code. Current version: **v1.0.0** (first public release; internal builds up to it were 1.24.x).

## Parts

| Part | Where | Notes |
|---|---|---|
| Live Editor Lua adapter | `integration/lua/` | Autorun bootstrap + runtime. A versioned copy `FC27_Academy_Engine_Runtime_v1.24.X.lua` sits at the repo root. |
| Python engine | `fc27_academy/`, `run_bridge_service.py` | All decisions; checkpoints in SQLite. |
| Launcher | `academy_manager/`, `run_manager.py` | PySide6. `overlay_export.py` turns the read model into overlay text and handles overlay commands. |
| Overlay | `native_overlay/source/` | `academy_overlay.c` (freestanding C, GDI) built straight into `AcademyOverlayHost.exe` (entry `OverlayMain`, no DLL since v1.0.6); `academy_overlay.rc` + `overlay_host.manifest` give it Windows file details and a manifest. Built binaries ship in `native_overlay/`. |

See docs/ARCHITECTURE_V124.md for storage, lifecycle, write path, decline, retirement and faces.

## Release routine

Every change is a versioned build:

1. Bump the version string in: `VERSION.txt`, `fc27_academy/__init__.py`, `fc27_academy/live_playstyle_writer.py`, `academy_manager/overlay_export.py`, `run_bridge_service.py`, `tools/self_test_v124.py`, both Lua files, `RESET_ALL_ACADEMY_DATA.bat`, `native_overlay/source/*` (including `academy_overlay.rc` and `overlay_host.manifest`), `native_overlay/README.txt`. Forms (from 1.0.0): `1.0.0`, `V100`, `v100_` (e.g. 1.0.1 -> `1.0.1`, `V101`, `v101_`). `tools/test_v100.py` checks they all agree. Restore history comments a blanket replace changes.
2. Replace the root `FC27_Academy_Engine_Runtime_v1.24.X.lua` with a copy of the current runtime under the new name.
3. Add `docs/RELEASE_NOTES_V10X.md` (e.g. V101 for 1.0.1), a README section at the top of the version history, and a `docs/BUILD_VALIDATION.txt` entry.
4. Rebuild the overlay with `sh tools/build_overlay.sh` (clang, lld-link, llvm-dlltool, llvm-rc) whenever the C or version changed. It builds `AcademyOverlayHost.exe` straight from `academy_overlay.c` with Windows file details and a manifest. Do not reintroduce a DLL + loader or LoadLibrary/GetProcAddress: antivirus engines flagged the old Go loader (v1.0.5, Nexus quarantine).
5. Run the suite from a clean copy of the tracked files, each test with a fresh `LOCALAPPDATA` and `QT_QPA_PLATFORM=offscreen`: `tools/self_test_v124.py` plus every `tools/test_*.py`.
6. Commit and zip the tracked files as `FC27_Academy_v1.24.X_<Name>.zip` (developer zip).
7. Public zip: `python tools/make_release.py OUT_DIR` builds `FC27_Academy_Engine_v<version>.zip` from an allowlist of run-time files (player files in `release/` go to the top of the zip). Add any new run-time folder to its `INCLUDE` list.
8. Windows release (on a PC with internet): `python tools/build_windows_release.py OUT_DIR` adds the bundled Python (`runtime/`) and writes `FC27_Academy_Engine_v<version>_Windows.zip`. Package versions live in `tools/requirements-windows.lock` (with hashes); change them only together and re-test on Windows. If a new Qt module is imported, add it to `QT_ROOTS` in that script.

## Testing without Windows

- `tests/native/*_harness.c` compile the overlay C against stubs and check behaviour.
- `tests/native/gdi_log.c` + `snapshot_main.c` log GDI drawing; `tools/render_overlay_snapshot.py` renders it to PNG to view an overlay frame.
- Face tests set `FC27AE_SHOW_FACES=1`; debug / stress-test mode needs `FC27AE_DEBUG=1` (hidden and treated as off otherwise).

## Standing rules

- Never inject UI into FC27.exe; never store state under `%TEMP%`.
- Settings never roll back with a save; career state does.
- Never ship image assets; never modify the user's own face library or miniface files.
- Overlay wording: say "PlayStyle" / "PlayStyle+", not internal terms such as "normal PlayStyle".
- New risky features ship switched off by default.

## Status

- Shelved: matching in-game appearance to the face, controller (SDL) work.
- Hidden: faces (v1.24.37), debug / stress-test mode (v1.24.38).
- Not yet confirmed in-game: a real PlayStyle loss written to FC27, retirement across a real season rollover, the v1.24.36+ overlay on Windows.
- Known limits: a goalkeeper's outfield PlayStyles with no GK equivalent never decline; retirement needs the career date.
