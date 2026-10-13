"""Durable receipt index recovery across a crash after world persistence."""
import os,sys,tempfile,json,copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27receipt08_')
from fc27_academy import live_playstyle_writer as writer
from fc27_academy import transaction_index as ix
from fc27_academy.paths import BRIDGE_ROOT,ACADEMY_STATE_ROOT
from fc27_academy.world_bootstrap_store import WorldBootstrapStore
from fc27_academy.path_history_store import externalize,history
key='career';cid='transaction';wp=WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(key)
world={'save_uid':key,'career':{'date':{'day':2,'month':1,'year':2026}},'players':{'1':{'engine':{'playstyle_progress':{'Technical':100,'Inventive':75},'playstyle_progress_meta':{'Technical':{'history':[{'increment':5}]}}}}}}
externalize(world);writer._atomic_json(wp,world)
sr=BRIDGE_ROOT/'saves'/key;mp=sr/'live_ps_transactions'/f'{cid}.json'
manifest={'save_uid':key,'changeset_id':cid,'status':'STAGED','entries':[{'playerid':1,'kind':'NORMAL_ACQUISITION','style':'Technical','field':'trait1','expected':0,'proposed':1,'bit':1,'cooldown_days':120}]}
writer._atomic_json(mp,manifest)
receipt={'changeset_id':cid,'status':'APPLIED','reason':'COMMITTED'};writer._atomic_json(sr/'sync_receipts'/f'{cid}.receipt.json',receipt)
real=writer._atomic_json

def crash(path,obj):
 if Path(path)==mp and obj.get('status')=='COMMITTED':raise OSError('simulated crash before manifest commit')
 return real(path,obj)
with patch.object(writer,'_atomic_json',side_effect=crash):
 results=writer.reconcile_durable_receipts(BRIDGE_ROOT);assert results[0]['status']=='RECONCILE_ERROR'
assert json.loads(mp.read_text())['status']=='STAGED'
ix._indexes.clear();results=writer.reconcile_durable_receipts(BRIDGE_ROOT);assert results[0]['status']=='COMMITTED'
player=json.loads(wp.read_text())['players']['1'];assert len(player['history'])==1
assert player['engine']['playstyle_progress']=={'Technical':0.0,'Inventive':75}
assert history(player['engine']['playstyle_progress_meta']['Technical'])==[{'increment':5}]
assert writer.reconcile_durable_receipts(BRIDGE_ROOT)==[]
assert writer.apply_receipt(BRIDGE_ROOT,receipt)['status']=='IDEMPOTENT'
print('Receipt crash/restart: exactly one acquisition history, other PS readiness preserved, references intact, terminal manifest skipped: PASS')
