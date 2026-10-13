"""v1.0.0: first public release. Every component reports the same version (VERSION.txt)."""
from __future__ import annotations
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
v = (ROOT / "VERSION.txt").read_text(encoding="utf-8").split()[0]
assert re.fullmatch(r"\d+\.\d+\.\d+", v), v
tag = "V" + v.replace(".", "")
import fc27_academy
assert fc27_academy.__version__ == v, fc27_academy.__version__
checks = {
    "academy_manager/overlay_export.py": [f"'VERSION={v}'"],
    "fc27_academy/live_playstyle_writer.py": [f"'version':'{v}'"],
    "run_bridge_service.py": [f"version='{v}'", f"mode={tag}_EXTERNAL"],
    "integration/lua/FC27_Academy_Engine_Runtime.lua": [f"Engine v{v} -", f'"version":"{v}"', f'RUNTIME_TOKEN="v{v.replace(".", "")}_"', f"FC27AE_UNIFIED_{tag}_READY"],
    "integration/lua/FC27_Academy_Engine_Autorun.lua": [f"Engine v{v} bootstrap", f'"version":"{v}"', f"FC27AE_{tag}_AUTORUN_ARMED"],
    "native_overlay/source/academy_overlay.c": [f'"VERSION={v}\\nALIVE="'],
    "native_overlay/README.txt": [f"Engine v{v} external"],
    "native_overlay/source/academy_overlay.rc": [f'#define VERSTR "{v}"', f"#define VER {v.replace('.', ',')},0"],
    "native_overlay/source/overlay_host.manifest": [f'version="{v}.0"'],
    "RESET_ALL_ACADEMY_DATA.bat": [f"Engine v{v} - Factory Reset"],
}
for f, needles in checks.items():
    src = (ROOT / f).read_text(encoding="utf-8")
    for n in needles:
        assert n in src, (f, n)
for binf in ("native_overlay/AcademyOverlayHost.exe",):
    assert v.encode() in (ROOT / binf).read_bytes(), f"{binf} not rebuilt for {v}"
assert (ROOT / f"FC27_Academy_Engine_Runtime_v{v}.lua").read_bytes() == (ROOT / "integration/lua/FC27_Academy_Engine_Runtime.lua").read_bytes()
assert (ROOT / f"docs/RELEASE_NOTES_{tag}.md").exists()
print(f"Version {v}: Python, Lua, overlay, host, release notes and runtime copy all agree: PASS")
