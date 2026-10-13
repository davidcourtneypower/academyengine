"""Isolated heartbeat, Save As and Lua event-order regressions."""
import os,sys,tempfile,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27ae_07_')
from fc27_academy.engine_lease import EngineLease
from fc27_academy.save_context import _clone_storage
root=Path(tempfile.mkdtemp());state=root/'state';bridge=root/'bridge'
for path,obj in [(state/'saves/parent/generated_world.json',{'players':{'1':{'engine':{'history':['kept']}}}}),(root/'career_settings/parent.json',{'speed':9}),(root/'events/parent/events.json',{'events':['award']}),(bridge/'saves/parent/playstyle_enrichment_queue.json',{'items':[{'status':'STAGED','changeset_id':'old'}]})]:
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj))
_clone_storage(bridge,state,'parent','child')
assert json.loads((root/'career_settings/child.json').read_text())=={'speed':9}
assert (root/'events/child/events.json').read_bytes()==(root/'events/parent/events.json').read_bytes()
assert (state/'saves/child/generated_world.json').read_bytes()==(state/'saves/parent/generated_world.json').read_bytes()
assert json.loads((bridge/'saves/child/playstyle_enrichment_queue.json').read_text())['items'][0]['status']=='QUEUED'
lease=EngineLease(root/'lease',interval=.02);lease.start();stamp=lease.path.stat().st_mtime_ns;time.sleep(.07);assert lease.path.stat().st_mtime_ns>stamp;lease.close();assert not lease.path.exists()
print('Save As history/settings/queue and independent lease: PASS')
from lupa import LuaRuntime
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
expired=false;calls=0
os.getenv=function() return '/test' end
require=function() end
Log=function() end
GetSaveUID=function() return 'career' end
IsInCM=function() return true end
io.open=function(path,mode)
 if string.find(path,'engine_enabled.lease',1,true) then
  return {read=function() return tostring(os.time()-(expired and 99 or 0)) end,close=function() end}
 end
 return {write=function() end,flush=function() end,close=function() end}
end
local t={written_records=0,first_record=0,record_size=1,GetFirstRecord=function() return nil end}
LE={db={GetTable=function() return t end}}
AddEventHandler=function(name,fn) handler=fn end
''')
s=(ROOT/'integration/lua/FC27_Academy_Engine_Runtime.lua').read_text()
hooks='''
function arm_test()
 startup_settle_events=0;active_save_uid='career';awaiting_load=false;pending_initial_snapshot=false;stabilize_events=0;pending_day_snapshot=false;inflight_id=nil;consume_armed=true
 consume=function() calls=calls+1;return true end
 response_complete=function() return true end
 emit_snapshot=function() return true,'mock-baseline',0,0,0,'FULL' end
end
function inflight_test() inflight_id='pending' end
'''
s=s.replace('local function OnCareerEvent(a,b,...)',hooks+'\nlocal function OnCareerEvent(a,b,...)')
lua.execute(s);lua.execute('arm_test();handler(nil,15);assert(calls==1)')
lua.execute('arm_test();inflight_test();handler(nil,15);assert(calls==1)')
lua.execute('arm_test();expired=true;handler(nil,15);assert(calls==1);expired=false;handler(nil,15);assert(calls==2)')
lua.execute('arm_test();handler(nil,29);handler(nil,15);assert(calls==2)')
print('Lua day award handoff, inflight guard, lease recovery and load quarantine: PASS')
