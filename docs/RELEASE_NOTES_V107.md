# FC27 Academy Engine v1.0.7 — Build from source

Nexus Mods asked for the full source on GitHub and detailed build instructions. No change to how the
mod works.

- **BUILDING.md** explains how the Windows download is built, where every file in it comes from,
  and what the mod does on a player's PC (processes, files, registry, no network, no injection,
  which game fields it writes, when it asks for administrator rights).
- **The overlay program builds on Windows with LLVM alone** (`py tools\build_overlay.py`; no Visual
  Studio or Windows SDK), replacing the Linux-only shell script.
- **Reproducible**: the same LLVM version produces a byte-identical AcademyOverlayHost.exe on any
  machine (no debug data, build paths or timestamps inside), so anyone can check the released file
  against the source.
- **The release build compiles the overlay itself** when LLVM is installed, and prints the SHA-256
  of the zip and of AcademyOverlayHost.exe.
