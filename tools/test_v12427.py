"""v1.24.27 regressions: no development-history toggle for paths FC27 gave the player;
player list without the status column/legend; colour tweaks; overview header without status."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12427_")
from academy_manager import overlay_export as ex

ev = [{"type": "PLAYSTYLE_GAINED", "title": "PlayStyle Acquired", "value": "Technical", "career_date": {"day": 1, "month": 8, "year": 2026}},
      {"type": "PLAYSTYLE_GAINED", "title": "Starting PlayStyles assigned", "value": "Block", "career_date": {"day": 1, "month": 7, "year": 2026}},
      {"type": "ROLE_UPGRADED", "title": "Upgraded by FC27", "source": "FC27", "value": "Winger", "career_date": {"day": 2, "month": 8, "year": 2026}},
      {"type": "ROLE_UPGRADED", "title": "Role++ Acquired", "value": "Poacher", "career_date": {"day": 3, "month": 8, "year": 2026}}]
d = {"_acq_events": ev}
assert ex._acquired_by_engine(d, "NORMAL", "Technical") and ex._acquired_by_engine(d, "NORMAL", "Block")
assert not ex._acquired_by_engine(d, "NORMAL", "Rapid")                  # native FC27 PlayStyle
assert not ex._acquired_by_engine(d, "ROLE", "Winger")                   # Role++ upgraded by FC27
assert ex._acquired_by_engine(d, "ROLE", "Poacher")
src = (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
assert src.count("else 1])))") == 3                                      # NORMAL / PLUS / ROLE path lines carry the flag
assert "_status_flags" not in src
print("Development page: history toggle only for paths Academy Engine gave the player: PASS")

c_src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert '"ROLE++ PROGRESS"};' in c_src and "status_legend" not in c_src and "status_dots" not in c_src
assert "small(dc,p->status,58,235" not in c_src                         # overview header without status
assert "small(dc,p->pos,xx+5,ry+31,g_colw[2]-10,18,C_MUTED" in c_src
assert "ps_layout(dc,csv,x,top,w,C_INFO)" in c_src and "small(dc,p->nextps,xx+5,ry+31,g_colw[7]-10,18,C_INFO" in c_src
assert 'small(dc,e->value,690,y+20,230,18,C_MUTED' in c_src and '"PlayStyle Acquired",470,y+20,200,18,C_MUTED' in c_src
print("Player list without status column/legend; position grey, PlayStyles blue; events grey except player: PASS")

cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Native paths harness: SKIPPED"); sys.exit(0)
t = Path(tempfile.mkdtemp())
c = c_src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
(t / "overlay_llp64.c").write_text(c, encoding="utf-8"); shutil.copy(ROOT / "tests/native/paths_v12427_harness.c", t / "harness.c")
flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
first = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c")], capture_output=True, text=True)
missing = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
(t / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in missing))
r = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c"), str(t / "stubs.c")], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-3000:]
out = subprocess.run([str(t / "h")], capture_output=True, text=True); print(out.stdout.strip())
assert out.returncode == 0 and "PASS" in out.stdout
print("FC27 Academy Engine v1.24.27 regression: PASS")
