"""v1.0.6 regressions: the overlay is one small program, with nothing a loader would look like.

VirusTotal (via Nexus Mods) flagged the v1.0.5 AcademyOverlayHost.exe 7/71 even with file details:
a Go program whose only job was to load AcademyOverlay.dll from its folder and keep it alive. The
overlay code is now built straight into AcademyOverlayHost.exe:
1. no AcademyOverlay.dll anywhere (repository, release zip, engine checks);
2. the program imports only kernel32, user32, gdi32 and xinput1_4, and none of LoadLibrary,
   GetProcAddress, CreateThread, VirtualAlloc/Protect, WriteProcessMemory or CreateRemoteThread;
3. it is a Windows GUI program with entry OverlayMain, file details and an asInvoker manifest;
4. the controller is read through the imported XInputGetState.
"""
from __future__ import annotations
import os, struct, subprocess, sys, tempfile, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v106_")
import build_windows_release as B

exe = ROOT / "native_overlay/AcademyOverlayHost.exe"
assert not (ROOT / "native_overlay/AcademyOverlay.dll").exists() and not (ROOT / "native_overlay/source/host").exists()
try:
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
except (OSError, subprocess.CalledProcessError):
    files = []
files = files or [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()]   # outside git: the files on disk
assert files and not any(f.endswith(".go") or f.endswith("AcademyOverlay.dll") for f in files)
print("One overlay program: no DLL, no Go host: PASS")

assert B.pe_imports(exe) == {"kernel32.dll", "user32.dll", "gdi32.dll", "xinput1_4.dll"}, B.pe_imports(exe)
data = exe.read_bytes()
for bad in (b"LoadLibraryA", b"LoadLibraryW", b"GetProcAddress", b"CreateThread", b"VirtualAlloc", b"VirtualProtect",
            b"WriteProcessMemory", b"CreateRemoteThread", b"OpenProcess", b"ReadProcessMemory", b"SetWindowsHookEx"):
    assert bad not in data, bad
assert b"XInputGetState" in data
print("Imports: only kernel32, user32, gdi32, xinput1_4; no loader, memory or hook functions: PASS")

off = struct.unpack_from("<I", data, 0x3C)[0]
opt = off + 24
magic = struct.unpack_from("<H", data, opt)[0]; assert magic == 0x20B
characteristics = struct.unpack_from("<H", data, off + 22)[0]
subsystem = struct.unpack_from("<H", data, opt + 68)[0]
assert subsystem == 2 and not characteristics & 0x2000, (subsystem, hex(characteristics))      # GUI program, not a DLL
for key in ("FileDescription", "OriginalFilename", "AcademyOverlayHost.exe", "FC27 Academy Engine"):
    assert key.encode("utf-16-le") in data, key
assert b'level="asInvoker"' in data
src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert "void __stdcall OverlayMain(void){g_inst=GetModuleHandleA(NULL);ExitProcess(worker(NULL));}" in src
assert "DllMain" not in src and "LoadLibraryA" not in src and "g_xget=XInputGetState;" in src
assert "/entry:OverlayMain" in (ROOT / "tools/build_overlay.py").read_text()
print("Program: Windows GUI, entry OverlayMain, file details, asInvoker manifest; controller via imported XInputGetState: PASS")

from academy_manager import overlay_host as H
assert not hasattr(H, "DLL") and "AcademyOverlay.dll" not in (ROOT / "academy_manager/overlay_host.py").read_text()
import make_release as MR
assert "native_overlay/AcademyOverlay.dll" not in MR.INCLUDE + MR.REQUIRED and "native_overlay/AcademyOverlayHost.exe" in MR.REQUIRED
print("Engine and release: only AcademyOverlayHost.exe is needed and shipped: PASS")
print("FC27 Academy Engine v1.0.6 regression: PASS")
