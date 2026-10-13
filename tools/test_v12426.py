"""v1.24.26 regressions: Role++ upgrades FC27 makes itself are noted (history + event,
'Upgraded by FC27') without starting the engine's Role++ cooldown; engine-written
upgrades and load/rewind comparisons are not mistaken for them."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12426_")

from fc27_academy.world_bootstrap_store import WorldBootstrapStore, native_role_upgrades
from fc27_academy.role_sync import ROLE_ID_TO_LABEL
from fc27_academy.evolution_staging import _semantic
rid = next(i for i in range(1, 53) if i in ROLE_ID_TO_LABEL and i + 100 in ROLE_ID_TO_LABEL and _semantic(i))
name = _semantic(rid)

# unit: detection rules
assert native_role_upgrades({}, {"roles": [rid, 0]}, {"roles": [rid + 100, 0]}) == [{"role": name, "role_id": rid + 100, "from_role_id": rid}]
assert native_role_upgrades({}, {"roles": [0, rid]}, {"roles": [rid + 100, 0]})[0]["role_id"] == rid + 100        # slot reorder
assert native_role_upgrades({}, {"roles": [rid + 100]}, {"roles": [rid + 100]}) == []                               # unchanged
assert native_role_upgrades({}, {"roles": [5]}, {"roles": [rid + 100]}) == [] or rid == 5                          # not from its Role+
eng = {"history": [{"type": "ROLE_PRODUCTION_COMMIT", "proposed": rid + 100}]}
assert native_role_upgrades(eng, {"roles": [rid]}, {"roles": [rid + 100]}) == []                                   # engine wrote it
print("Detection: Role+ -> Role++ by FC27 found (slot order independent); engine-written upgrades excluded: PASS")

# integration through the store
from fc27_academy.paths import ACADEMY_STATE_ROOT
store = WorldBootstrapStore(ACADEMY_STATE_ROOT)
ATTRS = {a: 60 for a in 'crossing finishing headingaccuracy shortpassing volleys defensiveawareness standingtackle slidingtackle dribbling curve freekickaccuracy longpassing ballcontrol shotpower jumping stamina strength longshots acceleration sprintspeed agility reactions balance aggression composure interceptions positioning vision penalties'.split()}
def snap(roles, day):
    return [{"playerid": 9, "name": "Kid", "clubteamid": 1, "clubname": "X", "age": 17, "overallrating": 60, "potential": 80,
             "birthdate": 1, "nationality": 1, "preferredposition1": 25, "roles": roles, "lifecycle": "CLUB", "attributes": dict(ATTRS)}]
meta = lambda d: {"date": {"day": d, "month": 8, "year": 2026}}
store.ingest("K", snap([rid, 0], 1), "cp1", request_id="r1", career_meta=meta(1), trigger="SCREEN_LOADED_BASELINE", credit_development=True)
w = json.loads(store.path_for("K").read_text()); w["players"]["9"]["engine"]["role_acquisition_cooldown_days_remaining"] = 0
store.path_for("K").write_text(json.dumps(w))
res = store.ingest("K", snap([rid + 100, 0], 2), "cp2", request_id="r2", career_meta=meta(2), trigger="DAY_SETTLED", credit_development=True)
assert [u["role_id"] for u in res["native_role_upgrades"]] == [rid + 100], res.get("native_role_upgrades")
p = json.loads(store.path_for("K").read_text())["players"]["9"]
assert any(h.get("type") == "FC27_NATIVE_ROLE_UPGRADE" and h.get("role") == name for h in p["history"])
assert int(p["engine"].get("role_acquisition_cooldown_days_remaining", 0) or 0) == 0
# a load/rewind snapshot (no continuity) never reports one
store.ingest("K", snap([rid, 0], 1), "cp3", request_id="r3", career_meta=meta(1), trigger="SCREEN_LOADED_BASELINE", credit_development=False)
res = store.ingest("K", snap([rid + 100, 0], 2), "cp4", request_id="r4", career_meta=meta(2), trigger="SCREEN_LOADED_BASELINE", credit_development=False)
assert res["native_role_upgrades"] == []
print("Store: FC27 upgrade noted in history on a continuous timeline only; Role++ cooldown not started: PASS")

from fc27_academy.event_engine import record_native_role_upgrades, load_events
ups = [{"playerid": 9, "player_name": "Kid", "role": name, "role_id": rid + 100, "clubteamid": 1}]
record_native_role_upgrades("K", ups, career={"user_teamid": 1, "date": {"day": 2, "month": 8, "year": 2026}})
record_native_role_upgrades("K", ups, career={"user_teamid": 1, "date": {"day": 2, "month": 8, "year": 2026}})   # idempotent
ev = [e for e in load_events("K") if e.get("source") == "FC27"]
assert len(ev) == 1 and ev[0]["type"] == "ROLE_UPGRADED" and ev[0]["title"] == "Upgraded by FC27" and ev[0]["is_user_team"]
from academy_manager import overlay_export as ex
how, date = ex._acquisition({"_acq_events": ev}, "ROLE", name)
assert "by FC27" in how and date, (how, date)
how, _ = ex._acquisition({"_acq_events": []}, "ROLE", name)
assert "when Academy Engine began tracking" in how
src = (ROOT / "fc27_academy/bridge_service.py").read_text(encoding="utf-8")
assert "record_native_role_upgrades(storage_key" in src
print("Events: one 'Upgraded by FC27' Role++ event per upgrade; Development page names FC27 as the source: PASS")
print("FC27 Academy Engine v1.24.26 regression: PASS")
