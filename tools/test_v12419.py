"""v1.24.19 regressions.

1. Development stops at the lifetime caps: a player at their normal PlayStyle cap gains no
   normal progress; a player who is not PS+ eligible, or already has a PS+, gains no PS+
   progress; owned PlayStyles never gain normal progress.
2. Player details > Development: owned PlayStyles / PS+ / Role++ show 100% with how and when
   they were obtained (starting PlayStyle on promotion, developed, or already owned in FC27),
   owned FC27 styles without a path are listed, and the path history ends with the
   acquisition entry.
"""
import copy, json, os, re, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12419_")

# ---- 1. caps ------------------------------------------------------------------------
from fc27_academy.playstyle_development_planner import update_from_evidence, current_styles
from fc27_academy.bridge_service import OUTFIELD
from fc27_academy import playstyle_lifetime as pl

def player(trait1=0, icon=0, cap=7, plus_ok=True):
    attrs = {k: 70 for k in OUTFIELD}
    p = {"playerid": 470001, "game": {"preferredposition1": 25, "trait1": trait1, "trait2": 0, "icontrait1": icon, "icontrait2": 0,
                                      "overallrating": 80, "potential": 90, "age": 20, "attributes": attrs}, "engine": {}}
    pl.ensure_policy(p)
    e = p["engine"]; e["playstyle_lifetime_normal_cap"] = cap
    e["playstyle_plus_lifetime_eligible"] = plus_ok; e["playstyle_plus_lifetime_eligibility_roll"] = 0.0 if plus_ok else 0.999
    return p

growth = {"attribute_changes": {k: 3 for k in OUTFIELD}}
# under cap: normal progress happens
p = player(trait1=1, cap=3); update_from_evidence(p, growth, "c1", training_days=5)
assert any(v > 0 for v in p["engine"]["playstyle_progress"].values())
assert "Finesse Shot" not in p["engine"]["playstyle_progress"]          # owned style never gains normal progress
# at cap (3 owned, cap 3): no normal progress at all
p = player(trait1=7, cap=3); update_from_evidence(p, growth, "c1", training_days=5)
assert not p["engine"]["playstyle_progress"], p["engine"]["playstyle_progress"]
# not PS+ eligible: no PS+ progress
p = player(trait1=7, cap=7, plus_ok=False); update_from_evidence(p, growth, "c1", training_days=5)
assert not p["engine"]["playstyle_plus_progress"], p["engine"]["playstyle_plus_progress"]
# eligible: PS+ progress only on owned styles
p = player(trait1=7, cap=7, plus_ok=True); update_from_evidence(p, growth, "c1", training_days=5)
assert p["engine"]["playstyle_plus_progress"] and set(p["engine"]["playstyle_plus_progress"]) <= {"Finesse Shot", "Chip Shot", "Power Shot"}
# already has a PS+: no further PS+ progress
p = player(trait1=7, icon=1, cap=7, plus_ok=True); update_from_evidence(p, growth, "c1", training_days=5)
assert not p["engine"]["playstyle_plus_progress"], p["engine"]["playstyle_plus_progress"]
print("Caps: no normal progress at the lifetime cap or on owned styles; no PS+ progress when ineligible or once a PS+ is owned: PASS")

# ---- 2. development page -----------------------------------------------------------------
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle
from fc27_academy.event_engine import append_event
from academy_manager import overlay_export as ex
ex.detect_game = lambda *a, **k: True
ex.game_pid = lambda *a, **k: 4242
obj = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = obj.get("payload") or obj
pl0 = copy.deepcopy(base["players"][0]); pl0["playerid"] = 460002; pl0["trait1"] = 7; pl0["icontrait1"] = 1
svc = BridgeService(FileBridge())
r = svc.handle(BridgeRequest("a", "CHECKPOINT_SNAPSHOT", dict(base, players=[pl0], runtime_session="RS", day_epoch=0, trigger="SCREEN_LOADED_BASELINE")))
assert r["status"] == "OK", r
ex.publish_overlay_state({})
key = lifecycle()["storage_key"]
date = {"day": 12, "month": 7, "year": 2030}
append_event(key, {"event_id": "e1", "type": "PLAYSTYLE_GAINED", "title": "Starting PlayStyles assigned", "playerid": 460002, "value": "Chip Shot", "career_date": date})
append_event(key, {"event_id": "e2", "type": "PLAYSTYLE_GAINED", "title": "PlayStyle acquired", "playerid": 460002, "value": "Power Shot", "career_date": {"day": 3, "month": 9, "year": 2030}})
append_event(key, {"event_id": "e3", "type": "PLAYSTYLE_PLUS_GAINED", "title": "PlayStyle+ acquired", "playerid": 460002, "value": "Finesse Shot", "career_date": {"day": 1, "month": 1, "year": 2031}})

def command(body, n=[0]):
    n[0] += 1; g = int(lifecycle()["generation"])
    (ex.BRIDGE_ROOT / f"overlay_cmd_{n[0]:010d}_{n[0]:06d}.txt").write_text(f"GEN|{g}\n{body}\n")

command("SELECT|460002"); ex.process_overlay_command(); ex.publish_overlay_state({})
txt = ex.STATE_FILE.read_text(encoding="utf-8")
paths = txt[txt.index("PATHS_BEGIN"):txt.index("PATHS_END")].splitlines()[1:]
rows = {(l.split("|")[0], l.split("|")[2]): l.split("|") for l in paths}
for style in ("Finesse Shot", "Chip Shot", "Power Shot"):
    row = rows[("NORMAL", style)]
    assert row[4] == "100.0" and row[5] == "1", row
assert "Starting PlayStyle assigned" in rows[("NORMAL", "Chip Shot")][6] and "12/07/2030" in rows[("NORMAL", "Chip Shot")][6]
assert "Developed by Academy Engine" in rows[("NORMAL", "Power Shot")][6] and "03/09/2030" in rows[("NORMAL", "Power Shot")][6]
assert "Already owned in FC27" in rows[("NORMAL", "Finesse Shot")][6]
plus = rows[("PLUS", "Finesse Shot")]
assert plus[4] == "100.0" and plus[5] == "1" and "01/01/2031" in plus[6], plus
# owned rows listed after developing rows
kinds = [l.split("|") for l in paths if l.startswith("NORMAL|")]
owned_flags = [k[5] for k in kinds]
assert owned_flags == sorted(owned_flags), owned_flags
command("VIEW|history_path|NORMAL:Chip Shot"); ex.process_overlay_command(); ex.publish_overlay_state({})
txt = ex.STATE_FILE.read_text(encoding="utf-8")
hist = txt[txt.index("PATH_HISTORY_BEGIN"):txt.index("PATH_HISTORY_END")].splitlines()[1:]
assert hist and hist[-1].startswith("NORMAL|460002|Chip Shot|12/07/2030|") and "ACQUIRED • Starting PlayStyle assigned" in hist[-1], hist
print("Development page: owned PS / PS+ at 100% with source and date (promotion start, developed, FC27); history ends with the acquisition: PASS")

src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert "small(dc,q->name,tx,y+13,210,18,accent," in src and "q->owned?C_GOOD:accent" not in src
print("Overlay: acquired path names use the section colour, not green: PASS")
