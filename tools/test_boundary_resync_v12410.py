"""v1.24.10 regression: mid-career boundaries must not discard development.

Replays the pattern seen in a real FC27 session (Live Editor log 08-10-2026):
the runtime lost its in-flight snapshot to a silent load boundary (event 5/29 or
IsInCM()==false) and every following snapshot was labelled as a load baseline,
so 85% of observed attribute growth earned no progress.
"""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12410_boundary_")

from lupa import LuaRuntime

# ---------------------------------------------------------------- Lua adapter
prelude = r'''
responded={};sent={};in_cm=true;logs={}
os.getenv=function() return '/test' end
require=function() end
Log=function(m) logs[#logs+1]=m end
GetSaveUID=function() return 'career' end
IsInCM=function() return in_cm end
dofile=function(p) return {career_uid='career',runtime_session=_G.TEST_SESSION,branch_id='b',storage_key='career__b',writes_held=false} end
io.open=function(path,mode)
 if string.find(path,'engine_enabled.lease',1,true) then
  return {read=function() return tostring(os.time()) end,close=function() end}
 end
 if string.find(path,'responses',1,true) then
  if responded[path] then return {close=function() end} end
  return nil
 end
 if string.find(path,'pending_sync',1,true) then return nil end
 return {write=function() end,flush=function() end,close=function() end,read=function() return '' end}
end
LE={db={GetTable=function() return {} end}}
AddEventHandler=function(name,fn) handler=fn end
'''
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(prelude)
src = (ROOT / "integration/lua/FC27_Academy_Engine_Runtime.lua").read_text(encoding="utf-8")
src = src.replace("local function OnCareerEvent(a,b,...)", '''
_G.TEST_SESSION=SESSION
emit_snapshot=function(trigger)
 seq=seq+1; local rid="req"..seq
 sent[#sent+1]=trigger..":"..tostring(day_epoch)
 inflight_id=rid; inflight_since=os.time(); coalesced_days=0
 return true,rid,1,0,0,"MOCK"
end
function respond_last() if inflight_id then responded[RESPONSES.."\\\\"..inflight_id..".json"]=true end end
local function OnCareerEvent(a,b,...)''')
lua.execute(src)

def ev(*events):
    for e in events:
        lua.execute(f"handler(nil,{e})")

def sent():
    t = lua.eval("sent")
    return [t[i] for i in range(1, len(t) + 1)]

ev(26)                                   # hub: genuine load baseline
assert sent() == ["SCREEN_LOADED_BASELINE:0"], sent()
lua.execute("respond_last()")
ev(15, 68)                               # day passes, settles on next settled event
assert sent()[-1] == "DAY_SETTLED:1", sent()
lua.execute("respond_last()")
# A silent mid-career boundary while a day snapshot is pending (the log pattern).
ev(15, 29, 15)
s = sent()
assert s[-1] == "BOUNDARY_RESYNC:3", s     # labelled as a re-sync, and both days counted
logs = lua.eval("logs"); logtext = "\n".join(str(logs[i]) for i in range(1, len(logs) + 1))
assert "FC27AE_LOAD_BOUNDARY event=29" in logtext, logtext[-400:]
lua.execute("respond_last()")
# Transient IsInCM()==false path behaves the same and is logged once.
lua.execute("in_cm=false"); ev(15, 15); lua.execute("in_cm=true"); ev(15)
assert sent()[-1] == "BOUNDARY_RESYNC:6", sent()   # 3 + 2 days while detached + re-attach day
logs = lua.eval("logs"); logtext = "\n".join(str(logs[i]) for i in range(1, len(logs) + 1))
assert logtext.count("FC27AE_DETACH") == 1 and "FC27AE_REATTACH" in logtext, logtext[-400:]
print("Lua: boundary/detach logged; following snapshot labelled BOUNDARY_RESYNC; days across the boundary counted: PASS")

# ------------------------------------------------------------- Python engine
from fc27_academy.world_bootstrap_store import WorldBootstrapStore
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService, OUTFIELD


def snap(bonus):
    a = {k: 60 for k in OUTFIELD}; a["acceleration"] += bonus; a["sprintspeed"] += bonus
    return [{"playerid": 500001, "preferredposition1": 27, "lifecycle": "CLUB", "clubteamid": 1, "age": 18,
             "overallrating": 65, "potential": 80, "birthdate": 1, "nationality": 1, "trait1": 0, "icontrait1": 0,
             "roles": [39], "attributes": a}]


def rapid(store):
    w = json.loads(store.path_for("K").read_text())
    return float(w["players"]["500001"]["engine"].get("playstyle_progress", {}).get("Rapid", 0))

cases = {}
for label, trig, epoch, credit in (("day", "DAY_SETTLED", 2, True), ("resync", "BOUNDARY_RESYNC", 2, True),
                                   ("save", "PREPARE_FOR_SAVE", 2, True), ("reload_no_days", "BOUNDARY_RESYNC", 1, True),
                                   ("load_branch_change", "BOUNDARY_RESYNC", 2, False)):
    st = WorldBootstrapStore(tempfile.mkdtemp())
    st.ingest("K", snap(0), "c0", request_id="r0", runtime_session="S", day_epoch=0, trigger="SCREEN_LOADED_BASELINE")
    st.ingest("K", snap(0), "c1", request_id="r1", runtime_session="S", day_epoch=1, trigger="DAY_SETTLED")
    r = st.ingest("K", snap(3), "c2", request_id="r2", runtime_session="S", day_epoch=epoch, trigger=trig, credit_development=credit)
    cases[label] = (rapid(st), r["development_credited"])
assert cases["day"][0] > 10 and cases["resync"][0] == cases["day"][0] and cases["save"][0] == cases["day"][0], cases
assert cases["reload_no_days"] == (0.0, False) or cases["reload_no_days"][1] is False, cases
assert cases["load_branch_change"][1] is False and cases["load_branch_change"][0] < 1.0, cases
print("Engine: growth credited for re-sync and save snapshots with elapsed days; never without days or across a branch change: PASS")

# Training opportunities roll once per elapsed day, deterministically.
from fc27_academy.playstyle_development_planner import _passive_training_gain, _player_rng, RULES
p = {"playerid": 500001, "game": {"attributes": {k: 75 for k in OUTFIELD}}}
one = sum(_passive_training_gain(p, "Rapid", RULES["Rapid"], {"pace": 1.2}, f"c{i}", days=1, rng=_player_rng(1, f"c{i}"))[0] for i in range(400))
ten = sum(_passive_training_gain(p, "Rapid", RULES["Rapid"], {"pace": 1.2}, f"c{i}", days=10, rng=_player_rng(1, f"c{i}"))[0] for i in range(400))
assert 7.0 < ten / max(one, 1e-9) < 13.0, (one, ten)
a1 = _passive_training_gain(p, "Rapid", RULES["Rapid"], {"pace": 1.2}, "x", days=5, rng=_player_rng(1, "x"))
a2 = _passive_training_gain(p, "Rapid", RULES["Rapid"], {"pace": 1.2}, "x", days=5, rng=_player_rng(1, "x"))
assert a1 == a2
print(f"Engine: training opportunities scale with elapsed days ({ten/one:.1f}x for 10 days) and replay deterministically: PASS")

# Bridge level: a re-sync on the active branch credits; exact restore never does.
fix = ROOT / "tests" / "fixtures"
def payload(name, **kw):
    obj = json.loads((fix / name).read_text()); p = dict(obj.get("payload") or obj); p.update(kw); return p
svc = BridgeService(FileBridge())
r1 = svc.handle(BridgeRequest("b1", "CHECKPOINT_SNAPSHOT", payload("01_load.json", runtime_session="RS", day_epoch=0, trigger="SCREEN_LOADED_BASELINE")))
r2 = svc.handle(BridgeRequest("b2", "CHECKPOINT_SNAPSHOT", payload("02_day_growth.json", runtime_session="RS", day_epoch=3, trigger="BOUNDARY_RESYNC")))
b2 = r2["payload"]["bootstrap"]
assert r2["status"] == "OK" and b2["development_credited"] is True and b2["training_days"] == 3, b2
assert r2["payload"]["branch_resolution"]["state"] == "CONTINUE_ACTIVE_BRANCH"
assert (r2["payload"].get("save_anchor") or {}).get("status") == "NOT_WRITTEN", r2["payload"].get("save_anchor")
print("Bridge: BOUNDARY_RESYNC on the active branch credits 3 elapsed days and writes no save anchor: PASS")
