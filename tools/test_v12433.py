"""v1.24.33 regressions: face picker tweaks -- "Automatic face" closes the picker, one growing
list with "Load more faces" under the grid (no pages), friendly region names."""
import copy, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["FC27AE_SHOW_FACES"] = "1"   # v1.24.37: the face feature is hidden by default
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12433_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from fc27_academy import faces as F
from fc27_academy.face_regions import region_label, REGION_LABELS, FALLBACKS
from fc27_academy.paths import USER_ROOT
from fc27_academy.nationalities import nationality_name

for folder, label in {"SouthAsia": "South Asia", "WestAfrica": "West Africa", "Afrocaribbean": "Afro-Caribbean", "Italia": "Italy",
                      "Middle-East": "Middle East", "SouthConeSA": "Southern Cone (South America)", "Ireland": "Ireland",
                      "european": "European", "NewRegionName": "New Region Name", "Afro_Brazil": "Afro Brazil", "UKBlack": "UK Black"}.items():
    assert region_label(folder) == label, (folder, region_label(folder))
odd = [r for r in FALLBACKS if region_label(r) == r and any(c.isupper() for c in r[1:])]
assert not odd, odd                                  # every CamelCase region gets a spelled-out name
print("Region names: friendly labels for every known region, spelled-out fallback for others: PASS")

lib = Path(tempfile.mkdtemp(prefix="faces_"))
img = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); img.paste((210, 160, 130, 255), (16, 16, 48, 48))
for r, n in {"Ireland": 100, "Anglosphere": 30, "WestAfrica": 30, "SouthAsia": 10}.items():
    (lib / r).mkdir()
    for i in range(n): img.save(lib / r / f"PP16{r}{i:04d}.png")
USER_ROOT.mkdir(parents=True, exist_ok=True)
(USER_ROOT / "manager_settings.json").write_text(json.dumps({"face_enabled": True, "face_library_path": str(lib)}))
idx = F.load_library(lib)
ids = {nationality_name(i): i for i in range(1, 230)}

from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle
from academy_manager import overlay_export as ex
from academy_manager.live_data import active_world
ex.detect_game = lambda *a, **k: True; ex.game_pid = lambda *a, **k: 4242
obj = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = obj.get("payload") or obj
players = []
for i in range(10):
    p = copy.deepcopy(base["players"][0]); p["playerid"] = 460200 + i; p["name"] = f"P {i}"; p["gender"] = 0
    p["nationality"] = ids["Republic of Ireland"]; players.append(p)
svc = BridgeService(FileBridge())
assert svc.handle(BridgeRequest("a", "CHECKPOINT_SNAPSHOT", dict(base, players=players, runtime_session="RS", day_epoch=0, trigger="SCREEN_LOADED_BASELINE")))["status"] == "OK"
assert ex.publish_overlay_state({})
seq = [0]
def command(body, expect=True):
    seq[0] += 1; g = int(lifecycle()["generation"])
    (ex.BRIDGE_ROOT / f"overlay_cmd_{seq[0]:010d}_{seq[0]:06d}.txt").write_text(f"GEN|{g}\n{body}\n")
    assert ex.process_overlay_command() == expect; assert ex.publish_overlay_state({})
    return ex.STATE_FILE.read_text(encoding="utf-8")
def kv(state, k): return re.search(rf"^{k}=(.*)$", state, re.M).group(1)
PID = 460203
command(f"SELECT|{PID}")
st = command(f"VIEW|face_page_size|40\nVIEW|face_region|Ireland\nVIEW|face_picker|{PID}")
regs = dict(x.split(":", 1) for x in kv(st, "FACE_PICKER_REGIONS").split(";"))
assert regs["WestAfrica"] == "West Africa" and regs["SouthAsia"] == "South Asia" and regs["Ireland"] == "Ireland"
assert "FACE_PICKER_PAGE" not in st and kv(st, "FACE_PICKER_TOTAL") == "100" and kv(st, "FACE_PICKER_BATCH") == "50"
print("Exporter: regions sent as folder:label pairs; no pages: PASS")

# pick a face deep in the list, then reopen: enough batches load to include it
deep = idx["M"]["Ireland"][85]
command(f"FACE|{PID}|{deep}")
command("VIEW|face_picker|0")
st = command(f"VIEW|face_picker|{PID}")
assert kv(st, "FACE_PICKER_REGION") == "Ireland" and kv(st, "FACE_PICKER_SHOWN") == "50"    # v1.24.35: one batch, not everything up to the current face
tiles = re.findall(r"^FACE\|([^|]*)\|", st, re.M); assert len(tiles) == 51 and tiles[0] == deep  # current face pinned first
st_more = command("VIEW|face_region|WestAfrica")
assert kv(st_more, "FACE_PICKER_SHOWN") == "30" and kv(st_more, "FACE_PICKER_REGION_LABEL") == "West Africa"
st_ang = command("VIEW|face_region|Anglosphere")
assert kv(st_ang, "FACE_PICKER_SHOWN") == "30"
st_ire = command("VIEW|face_region|Ireland")
assert kv(st_ire, "FACE_PICKER_SHOWN") == "50"
# a player whose face is in the first batch: one batch, then Load more adds one
command("VIEW|face_picker|0"); P2 = 460207
command(f"FACE|{P2}|{idx['M']['Ireland'][3]}"); command(f"SELECT|{P2}")
st2 = command(f"VIEW|face_picker|{P2}")
assert kv(st2, "FACE_PICKER_SHOWN") == "50"
st_lm = command("VIEW|face_limit|100")
assert kv(st_lm, "FACE_PICKER_SHOWN") == "100" and len(re.findall(r"^FACE\|", st_lm, re.M)) == 100
print("Load more: the list grows by a batch; current face pinned first; region switch resets: PASS")

cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Overlay native check: SKIPPED (no C compiler)")
else:
    d = Path(tempfile.mkdtemp())
    csrc = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
    (d / "overlay_llp64.c").write_text(csrc.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;"), encoding="utf-8")
    for f in ("gdi_log.c", "snapshot_main.c"): shutil.copy(ROOT / "tests/native" / f, d / f)
    flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
    first = subprocess.run([cc, *flags, "-o", str(d / "snap"), str(d / "snapshot_main.c"), str(d / "gdi_log.c")], capture_output=True, text=True)
    miss = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
    (d / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in miss))
    subprocess.run([cc, *flags, "-o", str(d / "snap"), str(d / "snapshot_main.c"), str(d / "gdi_log.c"), str(d / "stubs.c")], check=True)
    (d / "deep.txt").write_text(st, encoding="utf-8")
    out = subprocess.run([str(d / "snap"), str(d / "deep.txt"), str(PID), "1"], capture_output=True, text=True, env=dict(os.environ, GDI_LOG=str(d / "deep.log")))
    scroll = int(re.search(r"fp_scroll=(\d+)", out.stdout).group(1))
    log = (d / "deep.log").read_text(encoding="utf-8")
    assert scroll == 0 and "\tCurrent" in log, out.stdout                    # pinned current face is first, no scrolling needed
    assert "\tWest Africa" in log and "\tWestAfrica" not in log and "\tShowing 50 of 100 faces in Ireland" in log
    assert "Load more faces (50 left)" in log and "Previous" not in log and "Next" not in log
    print("Overlay draw (real C): current face first, friendly region names, Load more, no paging buttons: PASS")

c = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert 'append(out,200,"|AUTO\\nVIEW|face_picker|0\\n");g_fp_open=0;' in c
print("Automatic face closes the picker: PASS")
print("FC27 Academy Engine v1.24.33 regression: PASS")
