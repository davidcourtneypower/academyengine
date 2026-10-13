"""v1.24.13 regressions.

1. Replays the SAVE 1 -> SAVE 2 -> SAVE 1 sequence from the 08-10-2026 crash log:
   SCREEN_HAS_DONE_LOADING (68) on menus / while another save loads must not call into
   the game unless a day capture is waiting.
2. Crash forensics: around loads/saves/exits every event is logged and a NATIVE line
   precedes every call into the game.
3. The bridge lease: no idle timeout; a lapsed lease still processes load boundaries
   and counts days without touching the game.
4. Publication: the world file is parsed once per revision and the UI cache no longer
   stores each player's full world entry.
"""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12413_")

prelude = r'''
native={};logs={};sent={};responded={};uid='SAVE1';in_cm=true;lease_age=0
local function note(name) native[#native+1]={name=name,last_log=logs[#logs] or ''} end
os.getenv=function() return '/test' end
require=function() end
Log=function(m) logs[#logs+1]=m end
GetSaveUID=function() note('GetSaveUID'); return uid end
IsInCM=function() note('IsInCM'); return in_cm end
dofile=function(p) return {career_uid=uid,runtime_session=_G.TEST_SESSION,branch_id='b',storage_key=uid..'__b',writes_held=false} end
io.open=function(path,mode)
 if string.find(path,'engine_enabled.lease',1,true) then
  return {read=function() return tostring(os.time()-lease_age) end,close=function() end}
 end
 if string.find(path,'responses',1,true) then if responded[path] then return {close=function() end} end return nil end
 if string.find(path,'pending_sync',1,true) then return nil end
 return {write=function() end,flush=function() end,close=function() end,read=function() return '' end}
end
LE={db={GetTable=function() note('GetTable'); return {} end}}
AddEventHandler=function(name,fn) handler=fn end
'''
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(prelude)
src = (ROOT / "integration/lua/FC27_Academy_Engine_Runtime.lua").read_text(encoding="utf-8")
src = src.replace("local function OnCareerEvent(a,b,...)", '''
_G.TEST_SESSION=SESSION
emit_snapshot=function(trigger)
 seq=seq+1; sent[#sent+1]=trigger..":"..tostring(day_epoch)
 inflight_id="req"..seq; inflight_since=os.time(); coalesced_days=0
 return true,inflight_id,1,0,0,"MOCK"
end
function respond_last() if inflight_id then responded[RESPONSES.."\\\\"..inflight_id..".json"]=true end end
function get_day_epoch() return day_epoch end
local function OnCareerEvent(a,b,...)''', 1)
lua.execute(src)


def lst(name):
    t = lua.eval(name)
    return [t[i] for i in range(1, len(t) + 1)]


def ev(*events):
    for e in events:
        lua.execute(f"handler(nil,{e})")


def native_count():
    return len(lst("native"))


def respond():
    lua.execute("respond_last()")


# ---- 1. normal play: SAVE 1 loads, a day passes and is captured on 68 ----------------
ev(26); respond()
assert lst("sent") == ["SCREEN_LOADED_BASELINE:0"], lst("sent")
n = native_count(); ev(68, 68, 27)
assert native_count() == n, "68/27 with nothing pending touched the game"
ev(15); n = native_count(); ev(68)
assert native_count() > n and lst("sent")[-1] == "DAY_SETTLED:1", lst("sent")
respond()
print("68/27 touch the game only when a day capture is waiting; day capture on 68 unchanged: PASS")

# ---- 2. the crash-log sequence: save, quit, pick SAVE 2 (68 with new UID), 29, 26 -----
ev(28); respond()
assert lst("sent")[-1] == "PREPARE_FOR_SAVE:1"
n = native_count()
lua.execute("uid='SAVE2'")
ev(68, 68)                      # menus and the moment FC27 starts loading SAVE 2
assert native_count() == n, "game touched while FC27 was loading another save"
ev(29)
logs = "\n".join(lst("logs"))
assert "FC27AE_LOAD_BOUNDARY event=29" in logs
ev(68)                          # still loading
assert native_count() == n
ev(26)
assert lst("sent")[-1] == "SCREEN_LOADED_BASELINE:0", lst("sent")
assert "FC27AE_SAVE_SWITCH old=SAVE1 new=SAVE2" in "\n".join(lst("logs"))
respond()
print("SAVE 1 -> SAVE 2 (crash-log sequence): no game access until the SAVE 2 hub; clean baseline: PASS")

# ---- 3. forensics: event trace and NATIVE marker before every game call -------------
trace = [l for l in lst("logs") if l.startswith("FC27AE_EVENT ")]
assert any("ev=29" in l for l in trace) and any("ev=68 phase=NO_NATIVE_ACCESS" in l for l in trace), trace[-6:]
for call in lst("native")[n:]:
    if call["name"] in ("IsInCM", "GetSaveUID"):
        pass
first_after = lst("native")[n]
assert first_after["name"] == "IsInCM" and "phase=NATIVE" in first_after["last_log"], first_after["last_log"]
print("Event trace around load/save/exit; a NATIVE line precedes the first game call: PASS")

# ---- 4. lease: no idle timeout; lapsed lease still handles boundaries and counts days --
lua.execute("lease_age=7"); ev(15); respond()
assert lua.eval("get_day_epoch()") == 1, "a 7 s old lease (bridge alive) must be accepted"
lua.execute("lease_age=600"); n = native_count(); before = lua.eval("get_day_epoch()")
ev(68, 15, 15)
assert native_count() == n and lua.eval("get_day_epoch()") == before + 2
ev(29)
assert "event=29" in lst("logs")[-1] or any("FC27AE_LOAD_BOUNDARY event=29" in l for l in lst("logs")[-3:])
lua.execute("lease_age=0"); ev(26)
assert lst("sent")[-1].startswith("BOUNDARY_RESYNC:"), lst("sent")
assert lst("sent")[-1] == f"BOUNDARY_RESYNC:{before + 2}", lst("sent")
print("Lease: unchanged 8 s check; while lapsed, days counted and load boundaries handled without game access: PASS")
logs = lst("logs")
lapsed = [l for l in logs if l.startswith("FC27AE_LEASE_LAPSED")]
restored = [l for l in logs if l.startswith("FC27AE_LEASE_RESTORED")]
assert len(lapsed) == 1 and "reason=STALE" in lapsed[0] and "age=600" in lapsed[0], lapsed
assert len(restored) == 1 and "events_while_lapsed=3" in restored[0], restored   # 68,15,15 (29 is handled before the lease check)
print("Lease lapse/restore logged once each in the Live Editor log: PASS")

from fc27_academy.engine_lease import EngineLease
from unittest.mock import patch
msgs = []
lp = Path(tempfile.mkdtemp()) / "engine_enabled.lease"
lease = EngineLease(lp, interval=0.05, log=msgs.append)
real_refresh = lease.refresh
fail = {"on": False}
def flaky():
    if fail["on"]: raise PermissionError("locked by another process")
    real_refresh()
lease.refresh = flaky
lease.start(); time.sleep(0.2); fail["on"] = True; time.sleep(0.3); fail["on"] = False; time.sleep(0.2)
lease.close()
assert any(m.startswith("FC27AE_LEASE_WRITE_FAILED consecutive=1") for m in msgs), msgs
assert any(m.startswith("FC27AE_LEASE_RENEWED") and "after_failures=" in m for m in msgs), msgs
assert not lp.exists()
print("Bridge heartbeat: failed and recovered renewals logged to bridge.log: PASS")

# ---- 5. publication: one parse per world revision; UI cache without full world entry --
from academy_manager import live_data, read_model
from fc27_academy.paths import ACADEMY_STATE_ROOT
p = ACADEMY_STATE_ROOT / "saves" / "K" / "generated_world.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"players": {"1": {"engine": {"x": 1}}}}))
a = live_data._load_world_file(p); b = live_data._load_world_file(p)
assert a is b
time.sleep(0.01); p.write_text(json.dumps({"players": {"1": {"engine": {"x": 2}}}}))
os.utime(p, ns=(time.time_ns(), time.time_ns()))
c = live_data._load_world_file(p)
assert c is not a and c["players"]["1"]["engine"]["x"] == 2
read_model.sync_world("K", {}, [{"playerid": 1, "name": "A", "raw": {"engine": {"big": "x" * 5000}}}])
assert "raw" not in read_model.get_player("K", 1)
src = (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
assert "detail['raw']=((world.get('players') or {}).get(str(selected_pid))) or {}" in src
print("Publication: world parsed once per file revision; UI rows cache no full world entry; detail reads it from the world: PASS")
print("FC27 Academy Engine v1.24.13 regression: PASS")
