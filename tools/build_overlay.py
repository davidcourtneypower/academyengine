"""Build native_overlay/AcademyOverlayHost.exe from native_overlay/source (v1.0.7).

    py tools\\build_overlay.py            (Windows)
    python3 tools/build_overlay.py       (Linux / macOS cross-build)

Needs LLVM (https://github.com/llvm/llvm-project/releases): clang, lld-link, llvm-lib and llvm-rc.
On Windows the LLVM installer puts them in C:\\Program Files\\LLVM\\bin, which is searched
automatically; elsewhere they are taken from PATH, or set LLVM_DIR to LLVM's bin folder.
No Windows SDK or Visual Studio is needed: the import libraries are made from the .def files.

The build is reproducible (/Brepro, no debug data, no paths or timestamps in the program), so the
same LLVM version always produces a byte-identical AcademyOverlayHost.exe. The SHA-256 printed at
the end can be compared with the file in the release.
"""
from __future__ import annotations
import hashlib, os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native_overlay" / "source"
OUT = ROOT / "native_overlay" / "AcademyOverlayHost.exe"
LIBS = ["kernel32", "user32", "gdi32", "xinput1_4"]
CFLAGS = ["--target=x86_64-pc-windows-msvc", "-O2", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
          "-mno-stack-arg-probe", "-Wall", "-Wno-unused"]


def tool(name: str) -> str:
    dirs = [os.environ.get("LLVM_DIR", "")]
    if os.name == "nt":
        dirs += [r"C:\Program Files\LLVM\bin", r"C:\Program Files (x86)\LLVM\bin"]
    for d in dirs:
        if d:
            for cand in (Path(d) / name, Path(d) / f"{name}.exe"):
                if cand.exists():
                    return str(cand)
    found = shutil.which(name)
    if not found:
        raise SystemExit(f"{name} not found. Install LLVM (https://github.com/llvm/llvm-project/releases) "
                         f"or set LLVM_DIR to its bin folder.")
    return found


def run(cmd: list[str], cwd: Path | None = None) -> None:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"failed: {' '.join(cmd)}\n{r.stdout}{r.stderr}")


def build(out: Path = OUT) -> str:
    clang, lld, lib, rc = tool("clang"), tool("lld-link"), tool("llvm-lib"), tool("llvm-rc")
    with tempfile.TemporaryDirectory() as t:
        b = Path(t)
        for name in LIBS:
            run([lib, f"/def:{SRC / (name + '.def')}", "/machine:x64", f"/out:{b / (name + '.lib')}"])
        run([rc, "/fo", str(b / "host.res"), "academy_overlay.rc"], cwd=SRC)     # the .rc names the manifest relative to source/
        run([clang, *CFLAGS, "-c", "academy_overlay.c", "-o", str(b / "ov.obj")], cwd=SRC)
        run([lld, "/subsystem:windows", "/entry:OverlayMain", "/nodefaultlib", "/Brepro", f"/out:{out}",
             str(b / "ov.obj"), str(b / "host.res"), *[str(b / (n + ".lib")) for n in LIBS]])
    version = subprocess.run([clang, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"built {out}\n  compiler: {version}\n  SHA-256:  {digest}")
    return digest


if __name__ == "__main__":
    build(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else OUT)
