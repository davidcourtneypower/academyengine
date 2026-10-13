#!/bin/sh
# Rebuild native_overlay/AcademyOverlayHost.exe from native_overlay/source (v1.0.6).
# Needs clang, lld-link, llvm-dlltool and llvm-rc (cross-compiles from any OS).
# One small program built straight from academy_overlay.c: no DLL, no loader, no LoadLibrary, with
# Windows file details and a manifest that asks for no extra rights. (Until v1.0.5 a Go program
# loaded the overlay as a DLL; antivirus engines flagged that loader pattern.)
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC="$ROOT/native_overlay/source"
OUT="$ROOT/native_overlay"
B=$(mktemp -d)
for lib in kernel32 user32 gdi32 xinput1_4; do llvm-dlltool -m i386:x86-64 -d "$SRC/$lib.def" -l "$B/$lib.lib"; done
(cd "$SRC" && llvm-rc /fo "$B/host.res" academy_overlay.rc)
clang --target=x86_64-pc-windows-msvc -O2 -ffreestanding -fno-builtin -fno-stack-protector -mno-stack-arg-probe \
      -Wall -Wno-unused -c "$SRC/academy_overlay.c" -o "$B/ov.obj"
lld-link /subsystem:windows /entry:OverlayMain /nodefaultlib /debug /out:"$OUT/AcademyOverlayHost.exe" /pdb:"$OUT/AcademyOverlayHost.pdb" \
         "$B/ov.obj" "$B/host.res" "$B/kernel32.lib" "$B/user32.lib" "$B/gdi32.lib" "$B/xinput1_4.lib"
rm -rf "$B"
echo "built $OUT/AcademyOverlayHost.exe"
