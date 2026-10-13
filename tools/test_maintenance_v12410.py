"""v1.24.10 regression: exact-restore verification, bounded storage, accent-insensitive search."""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12410_maint_")

from fc27_academy import transaction_store as ts
from fc27_academy.paths import ACADEMY_STATE_ROOT, ensure_dirs
ensure_dirs()
fix = ROOT / "tests" / "fixtures"
def payload(name, **kw):
    obj = json.loads((fix / name).read_text()); p = dict(obj.get("payload") or obj); p.update(kw); return p

# 14. An anchor whose stored world does not match the FC27 state is rejected, not restored.
p = payload("01_load.json", save_uid="X", runtime_session="S")
world = {"career": p["career"], "players": {str(pl["playerid"]): {"game": dict(pl), "observed_this_checkpoint": True} for pl in p["players"]}}
wp = ACADEMY_STATE_ROOT / "saves" / "X__a" / "generated_world.json"; wp.parent.mkdir(parents=True, exist_ok=True)
wp.write_text(json.dumps(world))
assert ts.upsert_save_anchor(payload=p, storage_key="X__a", trigger="PREPARE_FOR_SAVE")["status"] == "ANCHORED"
assert ts.find_exact_save_anchor(p)["status"] == "FOUND"
bad = json.loads(json.dumps(world)); first = next(iter(bad["players"].values())); first["game"]["attributes"]["finishing"] += 7
with ts._connect() as con:   # simulate an anchor row holding a world from a different state
    con.execute("UPDATE save_anchors SET world_blob=? WHERE career_uid='X'", (ts._pack(bad),)); con.commit()
assert ts.find_exact_save_anchor(p)["status"] == "REJECTED_STATE_MISMATCH"
r = ts.restore_exact_save_anchor(payload=p, storage_key="X__b")
assert r["status"] == "REJECTED_STATE_MISMATCH" and not (ACADEMY_STATE_ROOT / "saves" / "X__b" / "generated_world.json").exists(), r
assert ts.find_exact_save_anchor(p, anchors_only=True)["status"] == "REJECTED_STATE_MISMATCH"
print("Exact save: mismatching anchor world is rejected instead of restored: PASS")

# 9. Snapshot journal and anchors are bounded per career.
for i in range(ts.SNAPSHOT_RETAIN_PER_CAREER + 25):
    ts.record_game_snapshot(payload=payload("01_load.json", save_uid="Y", runtime_session="S", request_id=f"r{i}"), storage_key="Y__a")
with ts._connect() as con:
    n = con.execute("SELECT COUNT(*) FROM game_snapshots WHERE career_uid='Y'").fetchone()[0]
assert n == ts.SNAPSHOT_RETAIN_PER_CAREER, n
wy = ACADEMY_STATE_ROOT / "saves" / "Y__a" / "generated_world.json"; wy.parent.mkdir(parents=True, exist_ok=True); wy.write_text("{}")
for i in range(ts.ANCHOR_RETAIN_PER_CAREER + 10):
    q = payload("01_load.json", save_uid="Y"); q["career"] = dict(q["career"]); q["career"]["date"] = {"day": 1 + i % 28, "month": 1 + i // 28, "year": 2031}
    ts.upsert_save_anchor(payload=q, storage_key="Y__a", trigger="PREPARE_FOR_SAVE" if i < 5 else "SCREEN_LOADED_BASELINE")
with ts._connect() as con:
    rows = con.execute("SELECT trigger FROM save_anchors WHERE career_uid='Y'").fetchall()
assert len(rows) == ts.ANCHOR_RETAIN_PER_CAREER and sum(r[0] == "PREPARE_FOR_SAVE" for r in rows) == 5, len(rows)
print(f"Storage: snapshot journal capped at {ts.SNAPSHOT_RETAIN_PER_CAREER}, anchors at {ts.ANCHOR_RETAIN_PER_CAREER} with real saves kept first: PASS")

# 9. Old response files are pruned.
import run_bridge_service as rbs
from fc27_academy.paths import BRIDGE_ROOT
old = BRIDGE_ROOT / "responses" / "old.json"; new = BRIDGE_ROOT / "responses" / "new.json"
old.write_text("{}"); new.write_text("{}"); os.utime(old, (time.time() - 3600, time.time() - 3600))
assert rbs._prune_responses(BRIDGE_ROOT) == 1 and new.exists() and not old.exists()
print("Storage: answered responses older than 15 minutes are pruned: PASS")

# 13. Search folds accents and case.
from academy_manager import read_model
rows = [{"playerid": 460001, "name": "Jürgen Müller", "club": "Atlético"}, {"playerid": 460002, "name": "Søren Ødegård", "club": "Bodø"},
        {"playerid": 460003, "name": "Plain Name", "club": "Club"}]
read_model.sync_world("S1", {"career": {}}, rows)
def q(text):
    found, _ = read_model.query_players({"storage_key": "S1", "query": text, "myclub": False}, 0, True, 50, 0)
    return sorted(r["playerid"] for r in found)
assert q("muller") == [460001] and q("MÜLLER") == [460001] and q("odegard") == [460002] and q("atletico") == [460001], (q("muller"), q("odegard"))
print("Search: accent/case-insensitive name and club matching: PASS")
