"""Compare a supplied v1.24.07 source tree with this build in isolated processes."""
import argparse,json,subprocess,sys,tempfile,importlib.util,os,copy,time
from unittest.mock import patch
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);args=p.parse_args()
ROOT=Path(__file__).resolve().parents[1];baseline=Path(args.baseline).resolve()
runner=r'''
import sys,os,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1]);os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27compare_')
from fc27_academy.file_bridge import FileBridge,BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.world_bootstrap_store import WorldBootstrapStore
from fc27_academy.paths import ACADEMY_STATE_ROOT
try:from fc27_academy.path_history_store import hydrate_world
except ImportError:hydrate_world=lambda x:x
results=[]
with patch('time.time',return_value=1790000000):
 service=BridgeService(FileBridge())
 for i,fn in enumerate(['01_load.json','02_day_growth.json','03_rewind.json','04_reload_newer.json']):
  obj=json.loads((Path(sys.argv[1])/'tests/fixtures'/fn).read_text());data=obj.get('payload') or obj
  data.setdefault('runtime_session','equivalence');data.setdefault('checkpoint_id',str(i))
  result=service.handle(BridgeRequest('compare-'+str(i),'CHECKPOINT_SNAPSHOT',data));assert result['status']=='OK',result
  payload=result['payload'];world=json.loads(WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(payload['storage_key']).read_text())
  results.append(hydrate_world(world))
print(json.dumps(results,sort_keys=True))
'''
a=json.loads(subprocess.check_output([sys.executable,'-c',runner,str(baseline)],text=True));b=json.loads(subprocess.check_output([sys.executable,'-c',runner,str(ROOT)],text=True))
assert a==b,'Persisted world/evidence/history differs after load/growth/rewind/resume'
print('Full bridge replay: hydrated worlds equal to v1.24.07 at every load/growth/rewind/resume checkpoint')
sys.path.insert(0,str(ROOT));os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27cooldown_')
from fc27_academy import playstyle_development_planner as current
from fc27_academy.playstyle_sync import PLAYSTYLE1
from fc27_academy import path_history_store as hs
spec=importlib.util.spec_from_file_location('fc27_academy.reference_planner',baseline/'fc27_academy/playstyle_development_planner.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
snapshot=json.loads((ROOT/'tests/fixtures/01_load.json').read_text())['players'][0]
count=0
for cooldown in [0,1,120]:
 for plus_cd in [0,1,180]:
  for owned in [0,PLAYSTYLE1['Technical']]:
   x={'playerid':snapshot['playerid'],'game':copy.deepcopy(snapshot),'engine':{'playstyle_acquisition_cooldown_days_remaining':cooldown,'playstyle_plus_cooldown_days_remaining':plus_cd}}
   x['game']['trait1']=owned
   x['engine']['playstyle_plus_eligible']=True
   y=copy.deepcopy(x)
   for day in range(30):
    evidence={'attribute_changes':{'dribbling':1,'ballcontrol':1}} if day%3==0 else {'attribute_changes':{}}
    with patch.object(old,'plus_addition_slots',return_value=1),patch.object(current,'plus_addition_slots',return_value=1):
     ra=old.update_from_evidence(x,evidence,str(day));rb=current.update_from_evidence(y,evidence,str(day));assert ra==rb and x==y
    if cooldown>0 and plus_cd==0 and owned and day==0:assert y['engine']['playstyle_plus_progress']['Technical']>0
    # Persist/refill bounded histories between ticks, as the real engine does.
    packed={'players':{'1':y}};hs.externalize(packed);y=hs.hydrate_world(packed)['players']['1']
    count+=1
print(f'Cooldown lanes, owned styles, deterministic training and migrated path history: {count} equivalent updates')
