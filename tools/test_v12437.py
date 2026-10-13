"""v1.24.37: the face (miniface) feature is hidden from the launcher and overlay. While hidden it
is off everywhere -- nothing assigned, shown or written to FC27 -- even if it was turned on before;
faces already saved with a career are kept. Gender stays visible."""
import copy, json, os, re, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12437_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("FC27AE_SHOW_FACES", None)
from PIL import Image
from fc27_academy import faces as F
from fc27_academy.paths import USER_ROOT
assert F.FACES_FEATURE_VISIBLE is False and not F.faces_visible()

lib = Path(tempfile.mkdtemp(prefix="faces_")); (lib / "Ireland").mkdir()
for i in range(5): Image.new("RGB", (8, 8)).save(lib / "Ireland" / f"{i}.png")
USER_ROOT.mkdir(parents=True, exist_ok=True)
(USER_ROOT / "manager_settings.json").write_text(json.dumps({"face_enabled": True, "face_write_ingame": True, "face_library_path": str(lib)}))
fs = F.face_settings()
assert fs["face_enabled"] is False and fs["face_write_ingame"] is False                 # previously switched on: still off while hidden
print("Hidden faces are off everywhere, whatever was saved before: PASS")

from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle
from academy_manager import overlay_export as ex
from academy_manager.live_data import active_world
ex.detect_game = lambda *a, **k: True; ex.game_pid = lambda *a, **k: 4242
obj = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = obj.get("payload") or obj
players = []
for i in range(3):
    p = copy.deepcopy(base["players"][0]); p["playerid"] = 460300 + i; p["name"] = f"P {i}"; p["gender"] = 1 if i == 1 else 0; players.append(p)
svc = BridgeService(FileBridge())
assert svc.handle(BridgeRequest("a", "CHECKPOINT_SNAPSHOT", dict(base, players=players, runtime_session="RS", day_epoch=0, trigger="SCREEN_LOADED_BASELINE")))["status"] == "OK"
w = active_world()
assert not any((p.get("engine") or {}).get("face") for p in w["players"].values())       # nothing assigned
assert ex.publish_overlay_state({})
g = int(lifecycle()["generation"]); (ex.BRIDGE_ROOT / "overlay_cmd_0000000001_000001.txt").write_text(f"GEN|{g}\nSELECT|460301\n")
assert ex.process_overlay_command(); assert ex.publish_overlay_state({})
st = ex.STATE_FILE.read_text(encoding="utf-8")
assert "FACES_ENABLED=0" in st and "SELECTED_FACE=\n" in st and "FACE_PICKER_PID=0" in st
assert "GROUP|faces|" not in st and "|face_enabled|" not in st and "|face_library|" not in st and "|face_write_ingame|" not in st
assert "SELECTED_GENDER=Female" in st                                                       # gender still shown
key = str(w.get("storage_key"))
g = int(lifecycle()["generation"]); (ex.BRIDGE_ROOT / "overlay_cmd_0000000002_000002.txt").write_text(f"GEN|{g}\nFACE|460301|Ireland/1.png\nSET|global|global|face_enabled|true\n")
ex.process_overlay_command()
assert not ex._face_choices_path(key).exists()                                               # picker commands ignored
assert F.face_settings()["face_enabled"] is False
print("Overlay: no Player faces settings, no face, no picker; face commands ignored; gender still shown: PASS")

# faces saved before hiding are kept in the career (shown again when the feature returns)
from fc27_academy.world_bootstrap_store import WorldBootstrapStore
from fc27_academy.paths import ACADEMY_STATE_ROOT
wp = WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(key)
data = json.loads(wp.read_text()); data["players"]["460300"].setdefault("engine", {})["face"] = {"file": "Ireland/1.png", "region": "Ireland", "gender": "M", "source": "auto", "identity": "x"}
wp.write_text(json.dumps(data))
assert svc.handle(BridgeRequest("b", "CHECKPOINT_SNAPSHOT", dict(base, players=players, runtime_session="RS", day_epoch=1, trigger="DAY_SETTLED")))["status"] == "OK"
assert json.loads(wp.read_text())["players"]["460300"]["engine"]["face"]["file"] == "Ireland/1.png"
print("Saved faces are kept while hidden: PASS")

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from academy_manager import launcher as L
L.start_engine = lambda *a, **k: None
win = L.Launcher(); win.timer.stop()
assert not hasattr(win, "face_on") and not hasattr(win, "face_lib")
texts = " ".join(w.text() for w in win.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel))
assert "Player faces" not in texts and "Face folder" not in texts
win.poll()                                                                                   # settings poll copes with no face card
print("Launcher: no Player faces card: PASS")
print("FC27 Academy Engine v1.24.37 regression: PASS")
