"""v1.24.11 regression: quitting Career Mode must never touch the game database.

Replays the sequence from the 08-10-2026 Live Editor log that preceded the crash:
DAY_PASSED -> quit (event 2 with a changed save UID) -> 146 -> 68 -> menu events.
"""
from pathlib import Path
from lupa import LuaRuntime
ROOT = Path(__file__).resolve().parents[1]
prelude = r'''
db_calls=0;captures={};statuses={};uid='career_A';in_cm=true;responded={}
os.getenv=function() return '/test' end
require=function() end
Log=function() end
GetSaveUID=function() return uid end
IsInCM=function() return in_cm end
dofile=function(p) return {career_uid=uid,runtime_session=_G.TEST_SESSION,branch_id='b',storage_key='k',writes_held=false} end
io.open=function(path,mode)
 if string.find(path,'engine_enabled.lease',1,true) then return {read=function() return tostring(os.time()) end,close=function() end} end
 if string.find(path,'responses',1,true) then if responded[path] then return {close=function() end} end return nil end
 if string.find(path,'pending_sync',1,true) then return nil end
 if string.find(path,'resident_runtime_status',1,true) then
  return {write=function(self,t) statuses[#statuses+1]=string.match(t,'"state":"([^"]+)"') end,flush=function() end,close=function() end}
 end
 return {write=function() end,flush=function() end,close=function() end,read=function() return '' end}
end
LE={db={GetTable=function() db_calls=db_calls+1; return {} end}}
AddEventHandler=function(name,fn) handler=fn end
'''
lua = LuaRuntime(unpack_returned_tuples=True); lua.execute(prelude)
src = (ROOT / "integration/lua/FC27_Academy_Engine_Runtime.lua").read_text(encoding="utf-8")
src = src.replace("local function OnCareerEvent(a,b,...)", '''
_G.TEST_SESSION=SESSION
emit_snapshot=function(trigger)
 local ok=refresh_tables(); seq=seq+1; captures[#captures+1]=trigger..":"..tostring(day_epoch)
 inflight_id="req"..seq; inflight_since=os.time(); coalesced_days=0
 return true,inflight_id,1,0,0,"MOCK"
end
function respond_last() if inflight_id then responded[RESPONSES.."\\\\"..inflight_id..".json"]=true end end
local function OnCareerEvent(a,b,...)''', 1)
lua.execute(src)
def ev(*es):
    for e in es: lua.execute(f"handler(nil,{e})")
def caps():
    t = lua.eval("captures"); return [t[i] for i in range(1, len(t) + 1)]
def last_status():
    t = lua.eval("statuses"); return t[len(t)]

ev(26); lua.execute("respond_last()"); ev(15, 68); lua.execute("respond_last()")
assert caps() == ["SCREEN_LOADED_BASELINE:0", "DAY_SETTLED:1"], caps()
ev(15)                                             # a day passes; capture deferred
db_before = lua.eval("db_calls")
lua.execute("uid='career_menu_tmp'")              # FC27 tears the career down
ev(2, 146, 68, 27, 68, 1, 3)                      # the logged quit sequence + menu noise
assert caps() == ["SCREEN_LOADED_BASELINE:0", "DAY_SETTLED:1"], caps()
assert lua.eval("db_calls") == db_before, "database touched during career exit"
assert last_status() == "LEFT_CAREER", last_status()
print("Quit: no snapshot and no DB access during teardown; LEFT_CAREER published: PASS")

# Unsettled in-career events never trigger native access either.
lua.execute("uid='career_A'"); ev(26)
assert caps()[-1] == "BOUNDARY_RESYNC:2", caps()   # same save reloaded: re-sync, day 2 kept
lua.execute("respond_last()")
n = lua.eval("db_calls"); ev(42, 44, 7, 8, 146, 152)   # match entry/sim/completion/highlights
assert lua.eval("db_calls") == n and caps()[-1] == "BOUNDARY_RESYNC:2"
print("Reload same save after quit resumes as re-sync; match/sim events never touch the DB: PASS")

# Loading a different career after quitting is a clean new baseline.
lua.execute("uid='career_B'"); ev(5, 29, 68, 26)
assert caps()[-1] == "SCREEN_LOADED_BASELINE:0", caps()
print("Loading another career after quitting starts a fresh load baseline: PASS")
