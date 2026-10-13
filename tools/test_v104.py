"""v1.0.4 regressions.

1. Overlay: PlayStyle and role names are laid out from their measured width, so names on the
   same line never run into each other (they used to be placed at a guessed 7 px per letter).
2. Deleting a career's engine data remembers who its players were: the same players come back
   as already known, but a different player (new career reusing the save ID, or a reused player
   ID) is treated as new. A v1.0.3 deletion record still works.
3. The bridge's lifecycle sync does not undo the "data deleted" state while the same career stays loaded.
4. Live Editor's log folder: the remembered folder is used without searching again.
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v104_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle
from fc27_academy.paths import DELETED_CAREERS_ROOT
from fc27_academy import world_bootstrap_store as WB
from academy_manager import overlay_export as ex
from academy_manager.live_data import active_world, delete_current_data
ex.detect_game = lambda *a, **k: True; ex.game_pid = lambda *a, **k: 4242

base = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = base.get("payload") or base
grown = json.loads((ROOT / "tests/fixtures/02_day_growth.json").read_text()); grown = grown.get("payload") or grown
svc = BridgeService(FileBridge())
def cp(p, i, trig, uid="TESTSAVE"):
    r = svc.handle(BridgeRequest(f"r{uid}{i}", "CHECKPOINT_SNAPSHOT", dict(p, save_uid=uid, runtime_session="RS", day_epoch=i, checkpoint_id=f"{uid}c{i}", trigger=trig)))
    assert r["status"] == "OK", r; return r
cp(base, 0, "CAREER_SETTLED_BASELINE"); cp(grown, 1, "DAY_SETTLED")
ex.publish_overlay_state({})

# ---- 1. overlay text layout ------------------------------------------------------------------------
LONG_PS = "Whipped Pass,Incisive Pass,Long Ball Pass,Tiki Taka,Pinged Pass,Inventive,Aerial Fortress,Long Throw,Power Header"
LONG_ROLES = "CAM Shadow Striker+, RW Inside Forward+, ST Advanced Forward+, CM Box-to-Box++, CM Playmaker+"
state = ex.STATE_FILE.read_text(encoding="utf-8")
lines = state.split("\n")
for i, l in enumerate(lines):
    f = l.split("|")
    if len(f) > 30 and re.fullmatch(r"4600\d\d", f[0]):
        f[16] = LONG_PS; f[20] = LONG_ROLES; lines[i] = "|".join(f)
stress = "\n".join(lines)
cc = shutil.which("clang") or shutil.which("gcc")
try:
    from PIL import ImageFont
    # A 15 px font at least as wide as FC27's Bahnschrift: the GDI stub measures text with it and the
    # check below uses the same widths, so the layout is checked against what would be drawn.
    FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
except Exception:
    FONT = None
if not cc or FONT is None:
    print("Overlay text layout check: SKIPPED (no C compiler or font)")
else:
    d = Path(tempfile.mkdtemp())
    csrc = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
    (d / "overlay_llp64.c").write_text(csrc.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;"), encoding="utf-8")
    for f in ("gdi_log.c", "players_list_v104.c"): shutil.copy(ROOT / "tests/native" / f, d / f)
    flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
    def build(main, out):
        first = subprocess.run([cc, *flags, "-o", str(d / out), str(d / main), str(d / "gdi_log.c")], capture_output=True, text=True)
        miss = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
        (d / f"{out}_stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in miss))
        subprocess.run([cc, *flags, "-o", str(d / out), str(d / main), str(d / "gdi_log.c"), str(d / f"{out}_stubs.c")], check=True)
    build("players_list_v104.c", "plist")
    # the GDI stub measures text with the renderer's own letter widths
    (d / "charw.txt").write_text(" ".join(str(int(round(FONT.getlength(chr(c)) * 100))) if c >= 32 else "0" for c in range(128)))
    (d / "stress.txt").write_text(stress, encoding="utf-8")
    env = dict(os.environ, GDI_CHARW=str(d / "charw.txt"), GDI_LOG=str(d / "list.log"), VIZ_W="1600", VIZ_H="1600")
    out = subprocess.run([str(d / "plist"), str(d / "stress.txt")], capture_output=True, text=True, env=env)
    assert "players=" in out.stdout, out
    texts = []
    for l in (d / "list.log").read_text(encoding="utf-8").splitlines():
        if l.startswith("T "):
            head, s = l.split("\t", 1); v = head.split(" ")
            texts.append((int(v[1]), int(v[2]), int(v[3]), s))
    # every piece of text drawn in the PLAYSTYLES and ROLES columns, below their headers
    hdr = {t[3]: t for t in texts if t[3] in ("PLAYSTYLES", "ROLES")}
    assert set(hdr) == {"PLAYSTYLES", "ROLES"}, hdr
    cols = {k: (h[0] - 6, h[2] + 6) for k, h in hdr.items()}          # header text sits 6 px inside its column
    chips = [t for t in texts if t[1] > hdr["PLAYSTYLES"][1] + 20 and not re.search(r"PlayStyles?$", t[3]) and t[3] != "-"
             and any(lo <= t[0] < hi for lo, hi in cols.values())]
    pieces = " ".join(c[3] for c in chips)
    for n in (LONG_PS + "," + LONG_ROLES).split(","):
        assert all(word in pieces for word in n.split()), n                  # every name is shown in full
    pairs = 0
    for name, (lo, hi) in cols.items():
        rows: dict[int, list] = {}
        for c in chips:
            if lo <= c[0] < hi: rows.setdefault(c[1], []).append(c)
        for top, items in rows.items():
            items.sort()
            for a, b in zip(items, items[1:]):
                w = FONT.getlength(a[3]); pairs += 1
                assert a[0] + w + 2 <= b[0], f"'{a[3]}' ({w:.0f} px from x={a[0]}) runs into '{b[3]}' at x={b[0]}"
            for c in items:
                assert FONT.getlength(c[3]) <= c[2] - c[0] + 1, f"'{c[3]}' cut off in {name}"
                assert c[2] <= hi, f"'{c[3]}' drawn past the {name} column"
    assert pairs >= 8 and len(chips) >= 40, (pairs, len(chips))
    print(f"Overlay: {len(chips)} pieces of PlayStyle/role text laid out from their measured width; none overlap, run past the column or are cut off: PASS")
src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert not re.search(r"(ni|slen\([^)]*\))\*7", src) and "GetTextExtentPoint32W" in src   # no guessed text widths left
print("Overlay: no text width is guessed any more (PlayStyles, roles, badges, tooltips): PASS")
assert "GetTextExtentPoint32W=GDI32.GetTextExtentPoint32W" in (ROOT / "native_overlay/source/gdi32.def").read_text()

# ---- 2. deleted career: only the same players come back as known --------------------------------------
w = active_world(); pids = sorted(w["players"])
assert delete_current_data()
marker = json.loads((DELETED_CAREERS_ROOT / "TESTSAVE.json").read_text())
assert sorted(marker["players"]) == pids and all("birthdate" in v or "nationality" in v or "age" in v for v in marker["players"].values()), marker
cp(grown, 2, "DAY_SETTLED")
w = active_world()
assert all(p.get("bootstrap_source") == "REBUILT_AFTER_DELETE" and not p.get("generation_new_this_checkpoint") for p in w["players"].values())
snap = dict(next(iter(w["players"].values()))["game"])
known = marker["players"][str(snap["playerid"])]
assert WB._known_before_delete(WB._deleted_career_players("TESTSAVE"), snap["playerid"], snap)
other = dict(snap, nationality=(known.get("nationality") or 0) + 1, birthdate=(known.get("birthdate") or 0) + 4000, age=16)
assert not WB._known_before_delete(WB._deleted_career_players("TESTSAVE"), snap["playerid"], other), "a different player with a reused ID must be new"
assert not WB._known_before_delete(WB._deleted_career_players("TESTSAVE"), 469999, snap), "a player the career did not have must be new"
assert WB._deleted_career_players("NEVERDELETED") is None
(DELETED_CAREERS_ROOT / "OLDMARK.json").write_text(json.dumps({"career_uid": "OLDMARK", "deleted_at": 1, "storage_keys": ["OLDMARK"]}))
assert WB._known_before_delete(WB._deleted_career_players("OLDMARK"), 469999, snap)
print("Delete: the same players come back as already known; a new player or a reused ID is treated as new; v1.0.3 records still work: PASS")

# ---- 3. lifecycle sync keeps the deleted state ---------------------------------------------------------
import run_bridge_service as RBS
assert delete_current_data()
life = lifecycle(); assert life["state"] == "CAREER_LOADING" and "deleted" in life["detail"]
RBS.detect_game = lambda *a, **k: True
RBS._last_runtime_marker_stamp = None
bridge_root = Path(tempfile.mkdtemp()); (bridge_root / "resident_runtime_status.json").write_text("{}")
for mstate in ("ACTIVE", "CAREER_SETTLING"):
    RBS.live_editor_status = lambda m=mstate: {"runtime_marker": {"state": m, "runtime_session": "RS", "save_uid": "TESTSAVE", "detail": ""}}
    RBS._last_runtime_marker_stamp = None
    after = RBS._sync_runtime_lifecycle(bridge_root)
    assert after["state"] == "CAREER_LOADING" and int(after["generation"]) == 0, (mstate, after)
    if mstate == "ACTIVE": assert "deleted" in after["detail"], after       # the same career: the deleted message stays
ex.publish_overlay_state({}); assert not re.search(r"^4600\d\d\|", ex.STATE_FILE.read_text(), re.M)
cp(grown, 3, "DAY_SETTLED"); ex.publish_overlay_state({})
assert re.search(r"^4600\d\d\|", ex.STATE_FILE.read_text(), re.M)
print("Lifecycle: Live Editor heartbeats keep the deleted career empty until it is rebuilt at the next checkpoint: PASS")

# ---- 4. remembered log folder --------------------------------------------------------------------------
from academy_manager import le_menu_watch as M, live_editor_integration as LEI
from academy_manager.settings_store import load as load_settings, save as save_settings
logs = Path(tempfile.mkdtemp()) / "Logs"; logs.mkdir(); (logs / "le.log").write_text("x")
s = load_settings(); s["live_editor_logs"] = str(logs); save_settings(s)
def no_search(*a, **k): raise AssertionError("searched again although the remembered folder is valid")
LEI.discover_live_editor_root = no_search; LEI.all_live_editor_data_roots = no_search
assert M.find_logs_dir() == logs
print("Log folder: the remembered folder is used without searching again: PASS")
print("FC27 Academy Engine v1.0.4 regression: PASS")
