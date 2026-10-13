"""Offline progression and production regressions; isolated from real career data."""
import os, sys, tempfile, json, ctypes
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27ae_12406_')
from fc27_academy.production_scheduler import select_groups,FAMILIES
from fc27_academy.playstyle_development_planner import update_from_evidence
from fc27_academy.checkpoint_engine import ingest_checkpoint
from fc27_academy.playstyle_sync import PLAYSTYLE1
from fc27_academy.runtime_config import normal_threshold
from academy_manager.live_data import player_rows
from fc27_academy.role_sync import ROLE_ID_TO_LABEL

snap=json.loads((ROOT/'tests/fixtures/01_load.json').read_text())['players'][0]
p={'playerid':snap['playerid'],'game':deepcopy(snap),'engine':{},'lifecycle':'CLUB','observed_this_checkpoint':True}
a=deepcopy(p);b=deepcopy(p);b['game'].update(clubteamid=2,is_user_team=False)
evidence={'attribute_changes':{'dribbling':2,'ballcontrol':1}}
update_from_evidence(a,evidence,'same');update_from_evidence(b,evidence,'same')
assert a['engine']['playstyle_progress']==b['engine']['playstyle_progress']
print('Equal attributes/DNA/checkpoint: own club and other club receive equal PS progress: PASS')
q=deepcopy(p);q['engine']['playstyle_progress']={'Technical':normal_threshold()}
update_from_evidence(q,evidence,'queued')
assert 'Technical' not in q['engine'].get('playstyle_progress_meta',{})
q['game']['trait1']=PLAYSTYLE1['Technical'];q['game']['icontrait1']=PLAYSTYLE1['Technical']
update_from_evidence(q,evidence,'owned')
assert 'Technical' not in q['engine'].get('playstyle_progress_meta',{})
role_id=next(i for i in ROLE_ID_TO_LABEL if 101<=i<=152)
r=deepcopy(snap);r['roles']=[role_id];r['attributes']['dribbling']+=3
out,_=ingest_checkpoint({'game':snap,'engine':{},'history':[]},r,checkpoint_id='done')
assert not out['engine']['role_progress_meta']
print('Completed PS/PS+ paths and Role++ stop adding progress history: PASS')
entries=[]
for k,kind in enumerate(FAMILIES):
 for i in range(30):
  pid=460000+k*100+i
  for f in (['role1','role2'] if kind=='ROLE_UPGRADE' else ['trait1']):
   entries.append({'kind':kind,'playerid':pid,'field':f,'role':'Test role' if kind=='ROLE_UPGRADE' else None})
state={};served={k:set() for k in FAMILIES}
for n in range(20):
 selected,state,holds=select_groups(entries,12,{k:12 for k in FAMILIES},state)
 assert len(selected)<=12
 assert set(e['kind'] for e in selected)==set(FAMILIES)
 for e in selected:served[e['kind']].add(e['playerid'])
 for pid in {e['playerid'] for e in selected if e['kind']=='ROLE_UPGRADE'}:
  assert sum(e['playerid']==pid for e in selected)==2
assert all(len(v)==30 for v in served.values())
selected,_,_=select_groups(entries,12,{k:0 if k=='NORMAL_ACQUISITION' else 12 for k in FAMILIES})
assert not any(e['kind']=='NORMAL_ACQUISITION' for e in selected)
print('Heavy queue: all four families served, player rotation, atomic roles, limits/paused families: PASS')
free=deepcopy(p);free['lifecycle']='FREE_AGENT'
rows=player_rows({'players':{str(p['playerid']):free},'career':{'user_teamid':1}})
assert rows[0]['status']=='Paused — Free agent'
rows=player_rows({'players':{str(p['playerid']):p},'career':{'user_teamid':1}})
assert rows[0]['status']=='No active progress'
print('Zero-progress/free-agent status: PASS')
# Parse Lua without executing or touching Live Editor.
lib=ctypes.CDLL('liblua5.4.so.0');lib.luaL_newstate.restype=ctypes.c_void_p
lib.luaL_loadfilex.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p];lib.lua_close.argtypes=[ctypes.c_void_p]
for path in (ROOT/'integration/lua').glob('*.lua'):
 L=lib.luaL_newstate();assert lib.luaL_loadfilex(L,str(path).encode(),None)==0,path;lib.lua_close(L)
print('Lua 5.4 syntax validation: PASS')
from fc27_academy import live_playstyle_writer as writer
from fc27_academy.playstyle_sync import FC27_VERIFIED_BITS
from fc27_academy.playstyle_lifetime import ensure_policy
from fc27_academy.live_playstyle_writer import save_root
bitrows=[(name,bit) for name,bit in PLAYSTYLE1.items() if ('trait1',bit) in FC27_VERIFIED_BITS][:2]
world={'save_uid':'TEST','career':{'user_teamid':1},'players':{}}
for idx in range(4):
 wp=deepcopy(p);wp['playerid']=460100+idx;wp['game']['playerid']=wp['playerid'];ensure_policy(wp)
 wp['engine']['playstyle_plus_lifetime_eligible']=True; wp['engine']['playstyle_plus_lifetime_eligibility_roll']=0.0  # v1.24.10: eligibility follows the identity roll + live multiplier
 if idx==1:wp['game']['trait1']=bitrows[0][1]
 world['players'][str(wp['playerid'])]=wp
n={'verified_candidates':[{'playerid':460100,'style':bitrows[0][0],'field':'trait1','bit':bitrows[0][1],'expected':0,'proposed':bitrows[0][1],'validation':'READY_CONTROLLED_VERIFIED'}]}
pl={'verified_candidates':[{'playerid':460101,'style':bitrows[0][0],'field':'icontrait1','bit':bitrows[0][1],'expected':0,'proposed':bitrows[0][1],'validation':'READY_PLUS_VERIFIED'}]}
role={'verified_candidates':[{'playerid':460102,'role':'Defender','field_changes':[{'field':'role1','expected':1,'proposed':101},{'field':'role2','expected':1,'proposed':101}]}]}
qitems=[{'queue_id':'q'+str(i),'playerid':460103,'style':name,'field':'trait1','bit':bit,'expected':0,'proposed':bit,'status':'QUEUED'} for i,(name,bit) in enumerate(bitrows)]
root=Path(tempfile.mkdtemp());recorded=[]
with patch.object(writer,'enqueue_newgen',return_value={}),patch.object(writer,'_prepare_queue_candidates',return_value=({},qitems,[])),patch.object(writer,'_load_queue',return_value={'items':qitems}),patch.object(writer,'_save_queue',side_effect=lambda *args:recorded.append(deepcopy(args[-1]))):
 result=writer.stage_bundle(root,world,n,pl,{},role,checkpoint_id='integration')
assert result['status']=='STAGED_EVOLUTION_BUNDLE',result
assert set(e['kind'] for e in result['entries'])==set(FAMILIES)-{'PLAYSTYLE_LOSS','PLUS_DOWNGRADE'},result   # v1.24.36: loss kinds only with decline on
assert sum(e['kind']=='ROLE_UPGRADE' for e in result['entries'])==2
assert len(recorded)==1 and all(x['status']=='STAGED' for x in recorded[0]['items'])
assert (save_root(root,'TEST')/'pending_sync.lua').exists()
print('Full staging: four families, atomic multi-field role, multi-style queue marked STAGED, durable Lua handoff: PASS')
