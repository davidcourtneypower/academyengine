"""v1.24.24 regressions: one starting-PlayStyle plan per player (a player found again
supersedes his unwritten plan instead of stacking), settings re-read per checkpoint."""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12424_")

from fc27_academy import live_playstyle_writer as w
root = Path(tempfile.mkdtemp()); world = {"save_uid": "SAVE1"}
def prop(pid, style):
    return {"playerid": pid, "style": style, "validation": "READY_NEWGEN_VERIFIED", "field": "trait1", "bit": 1, "expected": 0, "proposed": 1}
def items():
    return w._load_queue(root, "SAVE1")["items"]
def status(pid, style):
    return [x["status"] for x in items() if x["playerid"] == pid and x["style"] == style]

# first session: player 1 planned Rapid + Technical, player 2 planned Block
r = w.enqueue_newgen(root, world, {"cohort_playerids": [1, 2], "proposals": [prop(1, "Rapid"), prop(1, "Technical"), prop(2, "Block")]})
assert r["added"] == 3 and r["superseded"] == 0
# one of player 2's entries is mid-write (STAGED) and must not be touched
q = w._load_queue(root, "SAVE1"); [x.update(status="STAGED") for x in q["items"] if x["style"] == "Block"]; w._save_queue(root, "SAVE1", q)

# reload without saving: player 1 found again with a different plan (Rapid + Trickster)
r = w.enqueue_newgen(root, world, {"cohort_playerids": [1], "proposals": [prop(1, "Rapid"), prop(1, "Trickster")]})
assert status(1, "Rapid") == ["QUEUED"], items()                 # kept, not duplicated
assert status(1, "Technical") == ["SUPERSEDED_REPLANNED"]
assert status(1, "Trickster") == ["QUEUED"]
assert status(2, "Block") == ["STAGED"]                           # other players / in-flight writes untouched
assert r["superseded"] == 1 and r["added"] == 1
queued_for_1 = [x for x in items() if x["playerid"] == 1 and x["status"] == "QUEUED"]
assert len(queued_for_1) == 2
# found again with nothing to add (target already met): old plan cleared
r = w.enqueue_newgen(root, world, {"cohort_playerids": [1], "proposals": []})
assert not [x for x in items() if x["playerid"] == 1 and x["status"] == "QUEUED"] and r["superseded"] == 2
# a normal checkpoint (player not new) never touches his plan
w.enqueue_newgen(root, world, {"cohort_playerids": [3], "proposals": [prop(3, "Jockey")]})
w.enqueue_newgen(root, world, {"cohort_playerids": [], "proposals": []})
assert status(3, "Jockey") == ["QUEUED"]
print("Starting PlayStyles: a player found again replaces his unwritten plan (no stacking); in-flight writes and other players untouched: PASS")

from fc27_academy import newgen_playstyle_enrichment as ng
world2 = {"players": {"7": {"playerid": 7, "observed_this_checkpoint": True, "generation_new_this_checkpoint": True, "engine": {},
                            "game": {"overallrating": 60, "potential": 75, "birthdate": 1, "nationality": 1, "preferredposition1": 25, "trait1": 0, "attributes": {}}},
                      "8": {"playerid": 8, "observed_this_checkpoint": True, "generation_new_this_checkpoint": False, "engine": {}, "game": {}}}}
assert ng.audit_world(world2, "cp")["cohort_playerids"] == [7]
print("Enrichment reports the cohort of newly found players: PASS")

# settings re-read for the active career at every checkpoint
src = (ROOT / "fc27_academy/bridge_service.py").read_text(encoding="utf-8")
i_ctx = src.index("write_active_context(self.bridge.root,career_uid=str(save_uid),branch_id=branch_id")
i_force = src.index("load_runtime_settings(force=True)")
i_ingest = src.index("adopted=store.ingest(")
assert i_ctx < i_force < i_ingest
from fc27_academy import runtime_config as rc
from fc27_academy.paths import BRIDGE_ROOT
BRIDGE_ROOT.mkdir(parents=True, exist_ok=True)
def activate(key):
    (BRIDGE_ROOT / "active_context.lua").write_text(f'return {{storage_key="{key}"}}\n')
for career, mult in (("SAVE1", 1.0), ("SAVE2", 4.0)):
    p = rc.career_settings_path(f"{career}__branch__a"); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"development": {"playstyle_plus_eligibility_multiplier": mult}}))
activate("SAVE1__branch__a"); assert rc.plus_eligibility_multiplier() == 1.0
activate("SAVE2__branch__a")
assert rc.plus_eligibility_multiplier() == 1.0            # stale within the 1 s cache window...
rc.load_runtime_settings(force=True)
assert rc.plus_eligibility_multiplier() == 4.0            # ...which each checkpoint now refreshes
print("Settings: each checkpoint re-reads the active career's settings before finding players: PASS")
print("FC27 Academy Engine v1.24.24 regression: PASS")
