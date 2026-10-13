"""v1.24.32 regressions: the overlay face picker (updated for v1.24.33: one growing list with
"Load more faces" instead of pages; "Automatic face" closes the picker; v1.24.35: 50 per batch).

Pick -> pending choice beside the world file -> shown at once -> moved into the world at
the next checkpoint (source "user") -> kept; "Automatic face" returns to the engine's face.
The real overlay C code is driven natively: its picker clicks write the commands that the
real exporter then applies, and a draw log checks what the picker puts on screen."""
import copy, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["FC27AE_SHOW_FACES"] = "1"   # v1.24.37: the face feature is hidden by default
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12432_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from fc27_academy import faces as F
from fc27_academy.paths import USER_ROOT
from fc27_academy.nationalities import nationality_name

lib = Path(tempfile.mkdtemp(prefix="faces_"))
img = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); img.paste((210, 160, 130, 255), (16, 16, 48, 48))
for r, n in {"Ireland": 70, "Anglosphere": 30, "WestAfrica": 30, "Spain": 20}.items():
    (lib / r).mkdir()
    for i in range(n): img.save(lib / r / f"PP16{r}{i:04d}.png")
(lib / "WF" / "European").mkdir(parents=True)
for i in range(20): img.save(lib / "WF" / "European" / f"WFEuropean{i:04d}.png")
USER_ROOT.mkdir(parents=True, exist_ok=True)
(USER_ROOT / "manager_settings.json").write_text(json.dumps({"face_enabled": True, "face_library_path": str(lib)}))
idx = F.load_library(lib)
ids = {nationality_name(i): i for i in range(1, 230)}

# --- picker paging (pure) -------------------------------------------------------------------
w = {"career_uid": "C", "players": {}}
for i in range(30):
    pid = 460000 + i
    w["players"][str(pid)] = {"game": {"playerid": pid, "birthdate": 150000 + i, "nationality": ids["Republic of Ireland"], "gender": 0}, "engine": {}}
F.assign_faces(w, {"face_enabled": True, "face_library_path": str(lib)}, idx)
cur = w["players"]["460005"]["engine"]["face"]
pg = F.picker_page(w, 460005, idx, "", 0, {}, 24)
assert pg["regions"][0] == "Ireland" and set(pg["regions"]) == set(idx["M"]) and pg["gender"] == "M"
assert pg["region"] == cur["region"] and any(f["current"] and f["file"] == cur["file"] for f in pg["faces"])   # opens on the current face's page
assert sum(f["in_use"] for f in pg["faces"]) >= 1 and not any(f["in_use"] and f["current"] for f in pg["faces"])
pg2 = F.picker_page(w, 460005, idx, "Spain", 500, {}, 24)
assert pg2["region"] == "Spain" and pg2["shown"] == pg2["total"] == 20 and len(pg2["faces"]) == 20
w["players"]["460006"]["game"]["gender"] = 1
assert F.picker_page(w, 460006, idx, "Ireland", 0, {}, 24)["region"] == "European"                            # women: WF only
print("Picker pages: regions most likely first, opens on the current face, marks faces in use, women from WF: PASS")

# --- end to end: bridge + exporter + real overlay C ------------------------------------------
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle
from academy_manager import overlay_export as ex
from academy_manager.live_data import active_world
ex.detect_game = lambda *a, **k: True; ex.game_pid = lambda *a, **k: 4242
obj = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = obj.get("payload") or obj
players = []
for i in range(30):
    p = copy.deepcopy(base["players"][0]); p["playerid"] = 460100 + i; p["name"] = f"P {i}"; p["gender"] = 0
    p["nationality"] = ids["Republic of Ireland"]; players.append(p)
svc = BridgeService(FileBridge())
day = [0]
def checkpoint(rid):
    # first: the career load; then ordinary in-career checkpoints (a load would re-resolve the save branch)
    trig = "SCREEN_LOADED_BASELINE" if rid == "a" else "DAY_SETTLED"
    r = svc.handle(BridgeRequest(rid, "CHECKPOINT_SNAPSHOT", dict(base, players=players, runtime_session="RS", day_epoch=day[0], trigger=trig)))
    day[0] += 1
    assert r["status"] == "OK", r
    if rid != "a": assert ex.publish_overlay_state({})
checkpoint("a")
assert ex.publish_overlay_state({})
seq = [0]
def command(body):
    seq[0] += 1; g = int(lifecycle()["generation"])
    (ex.BRIDGE_ROOT / f"overlay_cmd_{seq[0]:010d}_{seq[0]:06d}.txt").write_text(f"GEN|{g}\n{body}\n")
    assert ex.process_overlay_command(); assert ex.publish_overlay_state({})
    return ex.STATE_FILE.read_text(encoding="utf-8")
PID = next(int(k) for k, p in sorted(active_world()["players"].items())
           if p["engine"]["face"]["region"] == "Ireland" and idx["M"]["Ireland"].index(p["engine"]["face"]["file"]) < 40)   # current face on page 1
auto_face = active_world()["players"][str(PID)]["engine"]["face"]
closed = command(f"SELECT|{PID}")
assert "FACES_ENABLED=1" in closed and "FACE_PICKER_PID=0" in closed and "SELECTED_FACE_SOURCE=Automatic" in closed
opened = command(f"VIEW|face_page_size|40\nVIEW|face_picker|{PID}")
assert f"FACE_PICKER_PID={PID}" in opened and "FACE_PICKER_REGION=Ireland" in opened and "FACE_PICKER_SHOWN=50" in opened and "FACE_PICKER_TOTAL=70" in opened
tiles = re.findall(r"^FACE\|([^|]*)\|([^|]*)\|(\d)\|(\d)$", opened, re.M)
assert len(tiles) == 50 and all(Path(b).is_file() for _, b, _, _ in tiles) and sum(int(c) for _, _, c, _ in tiles) == 1
print("Exporter: picker page with cached thumbnails, current face marked: PASS")

cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Overlay native checks: SKIPPED (no C compiler)")
    picked = tiles[2][0]
    command(f"FACE|{PID}|{picked}")
else:
    d = Path(tempfile.mkdtemp())
    csrc = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
    (d / "overlay_llp64.c").write_text(csrc.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;"), encoding="utf-8")
    for f in ("gdi_log.c", "face_picker_v12432_harness.c", "snapshot_main.c"): shutil.copy(ROOT / "tests/native" / f, d / f)
    flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
    def build(main, out):
        first = subprocess.run([cc, *flags, "-o", str(d / out), str(d / main), str(d / "gdi_log.c")], capture_output=True, text=True)
        miss = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
        (d / f"{out}_stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in miss))
        subprocess.run([cc, *flags, "-o", str(d / out), str(d / main), str(d / "gdi_log.c"), str(d / f"{out}_stubs.c")], check=True)
    build("face_picker_v12432_harness.c", "picker"); build("snapshot_main.c", "snap")
    (d / "open.txt").write_text(opened, encoding="utf-8"); (d / "closed.txt").write_text(closed, encoding="utf-8")
    cmd_dir = d / "cmds"; cmd_dir.mkdir()
    env = dict(os.environ, GDI_LOG=str(d / "picker.log"))
    out = subprocess.run([str(d / "picker"), str(d / "open.txt"), str(PID), str(cmd_dir) + "/"], capture_output=True, text=True, env=env)
    assert out.returncode == 0 and "PASS" in out.stdout, out.stdout + out.stderr
    picked = re.search(r"WANT=(.*)", out.stdout).group(1)
    cmds = [p.read_text() for p in sorted(cmd_dir.glob("overlay_cmd_*.txt"))]
    body = "".join(c.split("\n", 1)[1] for c in cmds)
    assert f"FACE|{PID}|{picked}\n" in body and "VIEW|face_limit|100\n" in body and "VIEW|face_region|" in body
    assert f"FACE|{PID}|AUTO\nVIEW|face_picker|0\n" in body and f"VIEW|face_page_size|40\nVIEW|face_picker|{PID}\n" in body
    print("Overlay (real C, native): tile/region/page/automatic/close clicks write the right commands: PASS")
    # Draw logs: header button when closed; full picker when open.
    for name, open_flag in (("closed", "0"), ("open", "1")):
        subprocess.run([str(d / "snap"), str(d / f"{name}.txt"), str(PID), open_flag], check=True, capture_output=True, env=dict(os.environ, GDI_LOG=str(d / f"{name}.log")))
    closed_log = (d / "closed.log").read_text(encoding="utf-8"); open_log = (d / "open.log").read_text(encoding="utf-8")
    assert "\tChange face" in closed_log and "CHOOSE A FACE" not in closed_log and closed_log.count("\nB ") == 1
    assert "\tCHOOSE A FACE" in open_log and open_log.count("\nB ") == 1 + 50 and "\tShowing 50 of 70 faces in Ireland" in open_log and "Load more faces (20 left)" in open_log and "\tCurrent" in open_log
    print("Overlay draw: 'Change face' in the header; picker draws 50 thumbnails with page and current markers: PASS")
    # Feed the overlay's own command files to the real exporter (only the pick, not the close).
    face_cmd = next(c for c in cmds if c.split("\n", 1)[1].startswith(f"FACE|{PID}|{picked}"))
    g = int(lifecycle()["generation"]); seq[0] += 1
    (ex.BRIDGE_ROOT / f"overlay_cmd_{seq[0]:010d}_{seq[0]:06d}.txt").write_text(f"GEN|{g}\n" + face_cmd.split("\n", 1)[1])
    assert ex.process_overlay_command(); assert ex.publish_overlay_state({})

# --- pending until the next checkpoint, then saved with the career ----------------------------
key = str(active_world().get("storage_key"))
choices_path = ex._face_choices_path(key)
assert F.load_choices(choices_path)[str(PID)]["file"] == picked
state = ex.STATE_FILE.read_text(encoding="utf-8")
assert "SELECTED_FACE_SOURCE=Your choice (saved at the next checkpoint)" in state
assert active_world()["players"][str(PID)]["engine"]["face"]["file"] == auto_face["file"]   # world untouched until the checkpoint
checkpoint("b")
face = active_world()["players"][str(PID)]["engine"]["face"]
assert face["file"] == picked and face["source"] == "user" and not choices_path.exists()
state = command(f"SELECT|{PID}")
assert "SELECTED_FACE_SOURCE=Your choice\n" in state
checkpoint("c")
assert active_world()["players"][str(PID)]["engine"]["face"]["file"] == picked                   # kept
print("Pick is pending, shown at once, saved into the career at the next checkpoint and kept: PASS")

# Unknown files are refused; another player's ID reuse drops a stale choice.
seq[0] += 1; g = int(lifecycle()["generation"])
(ex.BRIDGE_ROOT / f"overlay_cmd_{seq[0]:010d}_{seq[0]:06d}.txt").write_text(f"GEN|{g}\nFACE|{PID}|Ireland/not_a_real_face.png\n")
assert not ex.process_overlay_command() and not choices_path.exists()          # not in the library: refused
command(f"FACE|{PID}|AUTO")
st = ex.STATE_FILE.read_text(encoding="utf-8")
assert "SELECTED_FACE_SOURCE=Automatic (saved at the next checkpoint)" in st
checkpoint("d")
face = active_world()["players"][str(PID)]["engine"]["face"]
assert face["source"] == "auto" and face["file"] == auto_face["file"], (face, auto_face)   # the same automatic face as before
F.save_choice(choices_path, active_world()["players"][str(PID)], picked)
d2 = json.loads(choices_path.read_text()); d2[str(PID)]["identity"] = "someone|else|0|M"; choices_path.write_text(json.dumps(d2))
checkpoint("e")
assert active_world()["players"][str(PID)]["engine"]["face"]["source"] == "auto" and not choices_path.exists()
print("Automatic face restores the engine's original face; invalid or stale choices are dropped: PASS")

src = (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
assert "'FACE'" in src and "view['face_picker']=0" in src
print("FC27 Academy Engine v1.24.32 regression: PASS")
