"""Prevent native DB/save calls during autorun and save-selection events."""
from pathlib import Path
from lupa import LuaRuntime
ROOT=Path(__file__).resolve().parents[1]
prelude='''
allowed=false;db_calls=0;uid_calls=0;cm_calls=0;imports=0;captures=0;load_attempts=0
os.getenv=function() return '/test' end
require=function() assert(allowed,'helper import before loaded career');imports=imports+1 end
Log=function() end
GetSaveUID=function() assert(allowed,'UID before loaded career');uid_calls=uid_calls+1;return 'career' end
IsInCM=function() assert(allowed,'native context before trusted career event');cm_calls=cm_calls+1;return true end
io.open=function(path,mode)
 if string.find(path,'engine_enabled.lease',1,true) then
  return {read=function() return tostring(os.time()) end,close=function() end}
 end
 return {write=function() end,flush=function() end,close=function() end}
end
LE={db={GetTable=function() assert(allowed,'DB before loaded career');db_calls=db_calls+1;return {} end}}
AddEventHandler=function(name,fn) handler=fn end
'''
lua=LuaRuntime(unpack_returned_tuples=True);lua.execute(prelude)
s=(ROOT/'integration/lua/FC27_Academy_Engine_Runtime.lua').read_text()
# Keep actual startup/event handler and table acquisition; bypass only snapshot encoding.
s=s.replace('local function OnCareerEvent(a,b,...)','''
emit_snapshot=function(trigger)
 local ok,err=refresh_tables();assert(ok,err);captures=captures+1
 return true,'snapshot',0,0,0,'FULL_DISCOVERY'
end
local function OnCareerEvent(a,b,...)''')
lua.execute(s)
lua.execute('assert(db_calls==0 and uid_calls==0 and cm_calls==0 and imports==0)')
for event in [5,29,27,68,1,2,3,27,68]*4:lua.execute(f'handler(nil,{event})')
lua.execute('assert(db_calls==0 and uid_calls==0 and cm_calls==0 and imports==0);allowed=true;handler(nil,26);assert(captures==1 and db_calls==5)')
lua.execute('allowed=false;handler(nil,29);handler(nil,68);handler(nil,27);assert(captures==1);allowed=true;handler(nil,15);assert(captures==2)')
# Native context failure never falls through to UID/DB access.
lua.execute('handler(nil,29);IsInCM=function() error("unavailable") end;handler(nil,28);assert(captures==2)')
print('Runtime: module load and repeated selection/load events perform zero native calls; hub/late attachment works; failed context holds: PASS')
boot=LuaRuntime(unpack_returned_tuples=True);boot.execute(prelude)
boot.execute('dofile=function(path) load_attempts=load_attempts+1;_G.FC27AE_RUNTIME_CURRENT_STATE="ACTIVE" end')
boot.execute((ROOT/'integration/lua/FC27_Academy_Engine_Autorun.lua').read_text())
for event in [5,29,27,68,1,2,3]*4:boot.execute(f'handler(nil,{event})')
boot.execute('assert(load_attempts==0);handler(nil,26);assert(load_attempts==1)')
print('Autorun: save selection cannot load resident runtime; hub event loads it: PASS')
