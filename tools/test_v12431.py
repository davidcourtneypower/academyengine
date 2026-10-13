"""v1.24.31 regressions: gender recorded and shown; faces from the user's regen-face
library (nationality/gender weighted, deterministic, no repeats, saved with the career);
the overlay header face; launcher face card; experimental in-game writer that only ever
touches its own files."""
import collections, copy, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["FC27AE_SHOW_FACES"] = "1"   # v1.24.37: the face feature is hidden by default
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12431_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fc27_academy import faces as F, face_regions as FR, face_ingame as FI
from fc27_academy.nationalities import nationality_name, _NATIONS, _EXTRA
from fc27_academy.paths import USER_ROOT

# --- Lua: gender read defensively and sent in every snapshot --------------------------
lua = (ROOT / "integration/lua/FC27_Academy_Engine_Runtime.lua").read_text(encoding="utf-8")
assert 'players:GetRecordFieldValue(r,"gender")' in lua and "pcall(function()" in lua
assert ",\"gender\":'..num(vals.gender)..'" in lua
from lupa import LuaRuntime
assert LuaRuntime().execute("return load(...)", lua) is not None
print("Lua snapshot: gender field read safely and exported: PASS")

# --- weights table covers every real nationality --------------------------------------
names = {n for n in _NATIONS if n} | set(_EXTRA.values())
names -= {"Rest of World", "Free Agents", "Created Players", "International"}
missing = sorted(n for n in names if n not in FR.NATION_WEIGHTS)
assert not missing, missing
regs = {r for w in FR.NATION_WEIGHTS.values() for r, _ in w} | {r for r, _ in FR.DEFAULT_WEIGHTS}
assert regs <= set(FR.FALLBACKS) and regs <= set(FR.FAMILY_OF), regs - set(FR.FAMILY_OF)
print(f"Weights: all {len(names)} nationalities mapped; every region has fallbacks and a family: PASS")

# --- a synthetic library (tiny PNGs; never the user's own) ------------------------------
from PIL import Image
lib = Path(tempfile.mkdtemp(prefix="faces_"))
men = ["Ireland", "Anglosphere", "WestAfrica", "Afrocaribbean", "SouthAsia", "MixedRace", "Spain", "BrazilMixed", "SouthConeSA", "China"]
img = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); img.paste((210, 160, 130, 255), (16, 16, 48, 48))
for r in men:
    (lib / r).mkdir()
    for i in range(120): img.save(lib / r / f"PP16{r}{i:04d}.png")
for r in ["European", "African"]:
    (lib / "WF" / r).mkdir(parents=True)
    for i in range(40): img.save(lib / "WF" / r / f"WF{r}{i:04d}.png")
(lib / "notes.txt").write_text("not a region")
idx = F.load_library(lib)
assert set(idx["M"]) == set(men) and set(idx["F"]) == {"European", "African"} and idx["count"] == 120 * len(men) + 80
assert all(f.startswith("WF/") for fs in idx["F"].values() for f in fs)
assert json.loads((USER_ROOT / F.INDEX_CACHE_NAME).read_text())["index"]["count"] == idx["count"]
print("Library: men's region folders, women's WF\\<region> folders, cached index: PASS")

ids = {nationality_name(i): i for i in range(1, 230)}
w_irl_m = dict(F.region_weights(ids["Republic of Ireland"], "M", idx))
assert max(w_irl_m, key=w_irl_m.get) == "Ireland" and w_irl_m["Ireland"] > 0.8
assert all(v > 0 for v in w_irl_m.values()) and abs(sum(w_irl_m.values()) - 1) < 1e-9   # small cross-heritage share
w_irl_f = dict(F.region_weights(ids["Republic of Ireland"], "F", idx))
assert max(w_irl_f, key=w_irl_f.get) == "European" and w_irl_f["European"] > 0.9       # family fallback for WF
w_ng_f = dict(F.region_weights(ids["Nigeria"], "F", idx))
assert w_ng_f["African"] > 0.95
w_jp = dict(F.region_weights(ids["Japan"], "M", idx))
assert max(w_jp, key=w_jp.get) == "China"                                             # Japan -> Korea -> China chain
print("Weights: Ireland mostly Irish faces, women via WF families, small cross-heritage share: PASS")

# --- assignment ------------------------------------------------------------------------
def make_world(n=400):
    w = {"career_uid": "CAREER1", "players": {}}
    nats = [ids["Republic of Ireland"], ids["England"], ids["Brazil"], ids["Nigeria"], ids["Spain"]]
    for i in range(n):
        pid = 460000 + i
        w["players"][str(pid)] = {"game": {"playerid": pid, "birthdate": 150000 + i, "nationality": nats[i % 5], "gender": 1 if i % 8 == 0 else 0}, "engine": {}}
    return w
on = {"face_enabled": True, "face_library_path": str(lib), "face_write_ingame": False}
assert F.assign_faces(make_world(), {"face_enabled": False, "face_library_path": str(lib)})["assigned"] == 0
w1 = make_world(); r1 = F.assign_faces(w1, on)
assert r1["assigned"] == 400 and r1["missing"] == 0, r1
w2 = make_world(); F.assign_faces(w2, on)
assert all(w1["players"][k]["engine"]["face"] == w2["players"][k]["engine"]["face"] for k in w1["players"])   # deterministic
files = [p["engine"]["face"]["file"] for p in w1["players"].values()]
assert len(set(files)) == len(files)                                                                         # no repeats
for p in w1["players"].values():
    f = p["engine"]["face"]
    assert (f["gender"] == "F") == (p["game"]["gender"] == 1) and f["file"].startswith("WF/") == (f["gender"] == "F")
irl = [p["engine"]["face"]["region"] for p in w1["players"].values() if p["game"]["nationality"] == ids["Republic of Ireland"] and p["game"]["gender"] == 0]
assert collections.Counter(irl)["Ireland"] / len(irl) > 0.7, collections.Counter(irl)
w3 = make_world(); w3["career_uid"] = "CAREER2"; F.assign_faces(w3, on)
assert sum(w3["players"][k]["engine"]["face"]["file"] != w1["players"][k]["engine"]["face"]["file"] for k in w1["players"]) > 300
print("Assignment: deterministic per career, no repeats, women from WF, nationality respected: PASS")

r = F.assign_faces(w1, on); assert r["kept"] == 400 and r["assigned"] == 0
key = "460003"; before = w1["players"][key]["engine"]["face"]
w1["players"][key]["game"]["birthdate"] += 9999          # FC27 reused the ID for someone else
F.assign_faces(w1, on); assert w1["players"][key]["engine"]["face"]["identity"] != before["identity"]
pick = idx["M"]["Spain"][7]
assert F.set_user_face(w1, key, pick, idx); F.assign_faces(w1, on)
assert w1["players"][key]["engine"]["face"]["file"] == pick and w1["players"][key]["engine"]["face"]["source"] == "user"
assert F.face_file(w1["players"][key], on) == lib / pick and F.face_file(w1["players"][key], dict(on, face_enabled=False)) is None
print("Assignment: kept across checkpoints, redone when the ID is reused, user choice kept: PASS")

# --- bridge ingest stores gender and faces with the career ---------------------------
(USER_ROOT).mkdir(parents=True, exist_ok=True)
(USER_ROOT / "manager_settings.json").write_text(json.dumps({"face_enabled": True, "face_library_path": str(lib)}))
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle
from academy_manager import overlay_export as ex
ex.detect_game = lambda *a, **k: True
ex.game_pid = lambda *a, **k: 4242
obj = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = obj.get("payload") or obj
players = []
for i in range(6):
    p = copy.deepcopy(base["players"][0]); p["playerid"] = 460100 + i; p["name"] = f"P {i}"; p["gender"] = 1 if i == 2 else 0
    p["nationality"] = ids["Republic of Ireland"]; players.append(p)
svc = BridgeService(FileBridge())
res = svc.handle(BridgeRequest("a", "CHECKPOINT_SNAPSHOT", dict(base, players=players, runtime_session="RS", day_epoch=0, trigger="SCREEN_LOADED_BASELINE")))
assert res["status"] == "OK", res
from academy_manager.live_data import active_world
world = active_world()
pl = world["players"]
assert pl["460102"]["game"]["gender"] == 1 and pl["460102"]["engine"]["face"]["gender"] == "F"
assert all(p["engine"]["face"]["file"] for p in pl.values())
print("Bridge ingest: gender stored, faces assigned before the world is saved: PASS")

assert ex.publish_overlay_state({}) and lifecycle()["state"] == "READY"
g = int(lifecycle()["generation"]); (ex.BRIDGE_ROOT / "overlay_cmd_0000000001_000001.txt").write_text(f"GEN|{g}\nSELECT|460101\n")
assert ex.process_overlay_command(); assert ex.publish_overlay_state({})
state = ex.STATE_FILE.read_text(encoding="utf-8")
gender = re.search(r"^SELECTED_GENDER=(.*)$", state, re.M).group(1); face = re.search(r"^SELECTED_FACE=(.*)$", state, re.M).group(1)
assert gender == "Male" and face.endswith(".bmp") and Path(face).is_file(), (gender, face)
bmp = Image.open(face); assert bmp.size == (96, 96) and bmp.mode == "RGB"
assert "SETTING|global|face_enabled|Player faces|bool|true" in state and "|face_library|Face library|info|Ready|" in state
assert "GROUP|faces|PLAYER FACES|" in state and "|face_write_ingame|" in state
print("Exporter: gender + 96px face BMP for the selected player; Player faces settings section: PASS")
assert ex._apply_setting("global", "global", "face_enabled", "false")
from academy_manager.settings_store import load as load_mgr
assert load_mgr()["face_enabled"] is False and load_mgr()["face_library_path"] == str(lib)
assert ex._apply_setting("global", "global", "face_enabled", "true")
print("Overlay settings toggle the global face switch: PASS")

# --- experimental in-game writer --------------------------------------------------------
le = Path(tempfile.mkdtemp(prefix="le_")); (le / "mods").mkdir()
heads = le / "mods/legacy/data/ui/imgAssets/heads"; heads.mkdir(parents=True)
(heads / "p460104.dds").write_bytes(b"users own miniface")          # user's file for a tracked player
(heads / "p999999.dds").write_bytes(b"unrelated")                    # never ours
off = FI.sync(world, lib, [le], enabled=False); assert off["written"] == 0
res1 = FI.sync(world, lib, [le], enabled=True)
assert res1["written"] == 2 * len(pl) - 1 and res1["skipped_user_files"] == 1, res1
dds = heads / "p460101.dds"; assert dds.read_bytes()[:4] == b"DDS " and Image.open(dds).size == (256, 256)
assert (le / "mods/legacy/data/ui/imgAssets/youthheads/p460101.dds").is_file()
assert (heads / "p460104.dds").read_bytes() == b"users own miniface" and (heads / "p999999.dds").read_bytes() == b"unrelated"
assert FI.sync(world, lib, [le], enabled=True)["kept"] == res1["written"]
other = {"players": {"460101": world["players"]["460101"]}}            # a different career is loaded
res2 = FI.sync(other, lib, [le], enabled=True)
assert res2["removed"] == res1["written"] - 2 and dds.is_file() and not (heads / "p460100.dds").exists()
(heads / "p460101.dds").write_bytes(b"user replaced ours")
FI.sync({"players": {}}, lib, [le], enabled=True)
assert (heads / "p460101.dds").read_bytes() == b"user replaced ours"   # changed by the user: left alone
FI.sync(world, lib, [le], enabled=False)
assert not (le / "mods/legacy/data/ui/imgAssets/youthheads/p460101.dds").exists()
assert (heads / "p999999.dds").exists() and (heads / "p460104.dds").exists()
print("In-game writer: DXT5 256px heads+youthheads, mirrors the loaded career, never touches user files, off removes ours: PASS")

from academy_manager import face_sync
(USER_ROOT / "manager_settings.json").write_text(json.dumps({"face_enabled": True, "face_library_path": str(lib), "face_write_ingame": False}))
assert face_sync.tick(world, wait=True) is False                       # feature off and nothing written: no work
src = (ROOT / "run_bridge_service.py").read_text(encoding="utf-8")
assert "face_sync.tick(active_world()" in src
print("Bridge loop: background face sync only when the experimental writer is on: PASS")

# --- launcher -----------------------------------------------------------------------------
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
lsrc = (ROOT / "academy_manager/launcher.py").read_text(encoding="utf-8")
assert "Browse face folder…" in lsrc and "def choose_face_library" in lsrc and "'face_enabled','face_write_ingame','face_library_path'" in lsrc
from academy_manager import launcher as L  # noqa: F401  (imports cleanly)
bat = (ROOT / "FC27 Academy Engine.bat").read_text()
assert "import PySide6, psutil, PIL" in bat and "Pillow" in (ROOT / "requirements-gui.txt").read_text()
print("Launcher: Player faces card (folder, switch, experimental writer); Pillow installed on upgrade: PASS")

# --- native overlay (real C) ----------------------------------------------------------------
c_src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert 'draw_kv(dc,"Gender"' in c_src and "draw_face(dc,48,160,96)" in c_src and 'seq(s->kind,"info"))return;' in c_src
cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Overlay native check: SKIPPED (no C compiler)")
else:
    d = Path(tempfile.mkdtemp()); (d / "state.txt").write_text(state, encoding="utf-8")
    csrc = c_src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
    (d / "overlay_llp64.c").write_text(csrc, encoding="utf-8")
    shutil.copy(ROOT / "tests/native/faces_v12431_harness.c", d / "harness.c")
    flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
    first = subprocess.run([cc, *flags, "-o", str(d / "h"), str(d / "harness.c")], capture_output=True, text=True)
    miss = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
    (d / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in miss))
    subprocess.run([cc, *flags, "-o", str(d / "h"), str(d / "harness.c"), str(d / "stubs.c")], check=True)
    out = subprocess.run([str(d / "h"), str(d / "state.txt")], capture_output=True, text=True)
    assert out.returncode == 0 and "PASS" in out.stdout, out.stdout + out.stderr
    print("Overlay (real C, native): gender/face keys, read-only face library row, faces colour: PASS")
print("FC27 Academy Engine v1.24.31 regression: PASS")
