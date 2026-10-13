# Building FC27 Academy Engine

This page explains how the Windows download is built from this repository, and what the mod does on
a player's PC. Everything in the download is either source code from this repository, or a
third-party file downloaded during the build and checked against a fixed SHA-256 hash.

## What the download is made of

| In the download | Comes from | Built? |
|---|---|---|
| `academy_manager/`, `fc27_academy/`, `run_manager.py`, `run_bridge_service.py` | Python source in this repository | No: shipped as source, run by the bundled Python |
| `integration/lua/*.lua` | Lua source in this repository | No: Live Editor runs the Lua as is |
| `*.bat`, `VERSION.txt`, `README.txt`, `THIRD_PARTY_NOTICES.txt` | this repository (`release/` for the two text files) | No |
| `native_overlay/AcademyOverlayHost.exe` | `native_overlay/source/academy_overlay.c` (+ `.rc`, `.manifest`, `.def`) | Yes: `tools/build_overlay.py` |
| `native_overlay/source/` | the overlay's source, included for transparency | No |
| `runtime/python/` | Python 3.12.10 "embeddable package" for Windows, downloaded from python.org | No: unpacked unchanged, hash-checked |
| `runtime/python/Lib/site-packages/` | PySide6-Essentials 6.12.0, shiboken6 6.12.0, psutil 7.2.2, Pillow 12.3.0 wheels from PyPI | No: installed with `pip --require-hashes`; unused Qt files removed |
| `runtime/licenses/` | the packages' licence texts, plus LGPL v3 / GPL v3 (`release/licenses/`) | No |

The only program compiled from this repository is `AcademyOverlayHost.exe`. `python.exe` and
`pythonw.exe` are the Python Software Foundation's signed files.

## Requirements

- Windows 10 or 11, 64-bit
- Python 3.12 from https://www.python.org/downloads/windows/ (used only to run the build scripts)
- LLVM 18.1 for Windows (the `win64` installer from https://github.com/llvm/llvm-project/releases).
  The build uses `clang`, `lld-link`, `llvm-lib` and `llvm-rc` from `C:\Program Files\LLVM\bin`.
  No Visual Studio or Windows SDK is needed.
- An internet connection (python.org and PyPI)

## Steps

1. Get the source: `git clone <this repository>`, or download it as a ZIP from GitHub and unzip it.
   Open a command prompt in that folder.
2. Build the overlay program on its own (optional, step 3 does it as well):

   ```
   py tools\build_overlay.py
   ```

   It prints the compiler version and the SHA-256 of `native_overlay\AcademyOverlayHost.exe`.
3. Build the Windows download:

   ```
   py tools\build_windows_release.py dist
   ```

   This:
   - downloads `python-3.12.10-embed-amd64.zip` from python.org into `dist\cache` and stops unless its
     SHA-256 is `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`;
   - installs the four packages pinned with hashes in `tools/requirements-windows.lock` (pip refuses
     any other file);
   - removes the parts of Qt the launcher does not load (decided from the DLL import tables), and the
     packages' pip install records, keeping their licence texts;
   - rebuilds `AcademyOverlayHost.exe` from source with `tools/build_overlay.py`;
   - writes `dist\FC27_Academy_Engine_v<version>_Windows.zip` from an allowlist of files
     (`tools/make_release.py`), and prints the SHA-256 of the zip and of `AcademyOverlayHost.exe`.

### Reproducible overlay build

`tools/build_overlay.py` links with `/Brepro` and no debug data, so the program contains no build
paths or timestamps: the same LLVM version produces a byte-identical `AcademyOverlayHost.exe` on any
machine. The SHA-256 of the released file is listed in the release notes for each version. A
different LLVM version still builds a working program from the same source, but its bytes (and hash)
will differ.

### Tests (optional)

`tools/test_*.py` are the regression tests (developed on Linux; most also run on Windows):

```
py -m pip install -r requirements-gui.txt
set QT_QPA_PLATFORM=offscreen
py tools\test_v106.py
```

## What the mod does on a player's PC

- **Processes.** The launcher (`run_manager.py`, run by the bundled `pythonw.exe`) starts the engine
  (`run_bridge_service.py`, same Python) and `AcademyOverlayHost.exe`. All three are child processes
  of the launcher and stop with it.
- **No injection, no game memory access.** Nothing is loaded into `FC27.exe` and no process memory is
  read or written. The overlay is an ordinary topmost window drawn with GDI, positioned over the FC27
  window it finds by process ID. It imports only kernel32, user32, gdi32 and xinput1_4 (controller).
- **Game data** is read and changed only through FC 27 Live Editor's own Lua API, by the Lua file
  the launcher installs as `lua\autorun\FC27_Academy_Engine.lua` in Live Editor's folder (the only
  file written outside the mod's own folders; `UNINSTALL.bat` removes it). Writes are limited to
  PlayStyle, PlayStyle+ and role fields (`trait1`, `trait2`, `icontrait1`, `icontrait2`, roles) of
  players FC27 generated during the career (player ID 460000 and above). The Python engine refuses
  any other field or player (`fc27_academy/staged_sync.py`), and the Lua side separately refuses any
  player below 460000.
- **Files** go to `%LOCALAPPDATA%\FC27AcademyEngine` (data, logs and the file exchange with the Lua
  side) and to the mod's own folder. Save files are never edited directly.
- **Registry**: read only, `HKEY_CURRENT_USER\SOFTWARE\Live Editor`, to find Live Editor.
- **Network**: none at run time. Only the build script downloads (python.org, PyPI).
- **Administrator rights** are never needed. If FC27 runs as administrator, Windows blocks a normal
  program's overlay from appearing over it; the launcher then offers a button that restarts it
  through the standard Windows UAC prompt (`academy_manager/elevation.py`). It never elevates
  without that prompt.
