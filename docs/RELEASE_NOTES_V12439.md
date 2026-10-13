# FC27 Academy Engine v1.24.39 — Release candidate packaging

No gameplay changes. Existing careers and settings carry over; no reset is required.

- **No Python install needed.** The Windows release carries its own Python (the official
  embeddable Python 3.12.10 for Windows) and exact, hash-checked versions of PySide6 Essentials
  6.12.0, psutil 7.2.2 and Pillow 12.3.0 in a `runtime` folder. `FC27 Academy Engine.bat` uses it
  when present and falls back to an installed Python otherwise (now with pinned versions).
- **Smaller download.** Only the parts of Qt the launcher uses are kept (QtCore, QtGui, QtWidgets,
  the Windows platform and style plugins, SVG/ICO/JPEG images), worked out from the DLL import
  tables so nothing they load is removed: 237 MB of packages become 62 MB; the Windows zip is ~26 MB.
- **Uninstaller.** `UNINSTALL.bat` removes Academy Engine's autorun file from every Live Editor folder
  it may have used (only files that are Academy Engine's), removes any faces the experimental face
  writer put into Live Editor, and deletes the engine data only if you type DELETE.
- **Player readme.** The public zip has a README.txt for players (requirements, install, playing,
  saves, other mods, antivirus, updating, uninstall, support) and THIRD_PARTY_NOTICES.txt. The
  developer README stays in the project. A draft mod page is in docs/NEXUS_PAGE.txt.
- **Building the Windows release** (on the release PC, once per release):
  `python tools/build_windows_release.py OUT_DIR` downloads the embeddable Python from python.org,
  installs the locked packages, trims Qt and writes `FC27_Academy_Engine_v<version>_Windows.zip`.
