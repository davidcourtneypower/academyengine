"""v1.24.25 regressions: player list (Next Role, status dots, wrapped roles, two-row filters,
free agents without a club, red Not Eligible), details (lane chips, text PlayStyles,
collapsible development sections), events, capitalised statuses."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12425_")

from academy_manager import overlay_export as ex
base = dict(playerid=1, name="A", club="Arsenal", lifecycle="CLUB", observed_this_checkpoint=True, normal_count=2, cap=5)

assert ex._next_role(dict(active_role_progress={"Winger": 40, "Poacher": 70}, role_progress={"Old": 99})) == ("Poacher", 70.0)
line = ex._row_line(dict(base, lifecycle="FREE_AGENT", club="Free Agents", active_role_progress={"Winger": 40}))
parts = line.split("|")
assert parts[3] == "" and parts[13] == "Winger", parts
assert ex._row_line(dict(base))[0:20].split("|")[3] == "Arsenal"
print("Next Role from the player's current roles; free agents show no club: PASS")

# saved sort column follows the inserted NEXT ROLE column
ex.VIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
ex.VIEW_FILE.write_text(json.dumps({"storage_key": "K", "sort_column": 13}))
v = ex._load_view("K"); assert v["sort_column"] == 14 and v["layout"] == 2          # old ROLE PROGRESS -> ROLE++ PROGRESS
ex.VIEW_FILE.write_text(json.dumps({"storage_key": "K", "sort_column": 14}))
assert ex._load_view("K")["sort_column"] == 0                                       # old STATUS: column removed in v1.24.27
ex.VIEW_FILE.write_text(json.dumps({"storage_key": "K", "sort_column": 15, "columns": 16}))
assert ex._load_view("K")["sort_column"] == 0                                       # v1.24.25 STATUS
ex.VIEW_FILE.write_text(json.dumps({"storage_key": "K", "sort_column": 4}))
assert ex._load_view("K")["sort_column"] == 4
from academy_manager import read_model as rm
rm.sync_world("K", {}, [dict(playerid=1, name="A", club="X", active_role_progress={"Winger": 40}), dict(playerid=2, name="B", club="X", active_role_progress={"Poacher": 70})])
assert [r["playerid"] for r in rm.query_players({"storage_key": "K"}, 13, True)[0]] == [2, 1]
assert rm.sync_world("K", {}, [dict(playerid=1, name="A", club="X", active_role_progress={"Winger": 40}), dict(playerid=2, name="B", club="X", active_role_progress={"Poacher": 70})])["rows_written"] == 0
print("Sorting by Next Role; old saved sort columns shifted; unchanged rows not rewritten: PASS")

ld = (ROOT / "academy_manager/live_data.py").read_text(encoding="utf-8")
for low in ("'developing'", "'queued'", "'not eligible'", "'cooldown'", "Paused — free agent", "Ready — queued"):
    assert low not in ld, low
assert "title.strip().lower()" in (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
print("Statuses and event titles capitalised consistently (older events normalised): PASS")

c_src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert '"ROLE++ PROGRESS"' in c_src and '"NEXT ROLE"' in c_src and '"Not Eligible"' in c_src and "C_BAD" in c_src and '"STATUS"};' not in c_src
assert 'box(dc,44,y+24,40,32,bc,bc)' not in c_src                       # events: no PS badge
assert "style_badges(dc,p->owned" not in c_src and "style_badges(dc,p->plus" not in c_src
cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Native UI harness: SKIPPED"); sys.exit(0)
t = Path(tempfile.mkdtemp())
c = c_src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
(t / "overlay_llp64.c").write_text(c, encoding="utf-8"); shutil.copy(ROOT / "tests/native/players_ui_v12425_harness.c", t / "harness.c")
flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
first = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c")], capture_output=True, text=True)
missing = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
(t / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in missing))
r = subprocess.run([cc, *flags, "-o", str(t / "h"), str(t / "harness.c"), str(t / "stubs.c")], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-3000:]
out = subprocess.run([str(t / "h")], capture_output=True, text=True); print(out.stdout.strip())
assert out.returncode == 0 and "PASS" in out.stdout
print("FC27 Academy Engine v1.24.25 regression: PASS")
