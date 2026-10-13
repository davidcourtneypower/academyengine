"""History garbage collection must preserve every durable root and recent write."""
import os,sys,tempfile,json,time,gzip
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27historygc_')
from fc27_academy import path_history_store as h
from fc27_academy.paths import ACADEMY_STATE_ROOT
from fc27_academy.transaction_store import create_checkpoint,_connect
from academy_manager import read_model

def world(label):
 w={'save_uid':label,'career':{'date':{'day':1,'month':1,'year':2026}},'players':{'1':{'engine':{'role_progress_meta':{'Forward':{'history':[{'label':label}]}}}}}}
 h.externalize(w);return w

def meta(w):return w['players']['1']['engine']['role_progress_meta']['Forward']
roots={label:world(label) for label in ['world','checkpoint','anchor','cache','recent','orphan']}
p=ACADEMY_STATE_ROOT/'saves/world/generated_world.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(roots['world']))
create_checkpoint('checkpoint',world=roots['checkpoint'],events={},trigger='TEST')
with _connect() as con:
 con.execute('INSERT INTO save_anchors VALUES(?,?,?,?,?,?,?,?,?,?)',('career','fp','anchor','b',1,'{}','TEST',gzip.compress(json.dumps(roots['anchor']).encode()),gzip.compress(b'{}'),1))
# v1.24.13: UI rows no longer cache the full world entry ('raw'); references held by
# cached row fields (e.g. next_ps_meta) must still be retained.
read_model.sync_world('cache',{},[{'playerid':1,'raw':{'ignored':True},'next_ps_meta':meta(roots['cache'])}])
now=time.time()+90000
with closing(h._connect()) as con, con:
 con.execute('UPDATE development_histories SET created_at=? WHERE digest=?',(now,meta(roots['recent'])['history_ref']))
result=h.collect_unused(now=now);assert result['removed']==1,result
for label in ['world','checkpoint','anchor','cache','recent']:assert h.history(meta(roots[label]))==[{'label':label}]
try:h.history(meta(roots['orphan']))
except RuntimeError:pass
else:raise AssertionError('unreferenced old history not collected')
assert h.collect_unused(now=now+10)['status']=='NOT_DUE'
# An unreadable world must abort all deletion, including otherwise eligible orphans.
w=world('corrupt_guard');p.write_text('bad json')
try:h.collect_unused(now=now+90000)
except ValueError:pass
else:raise AssertionError('corrupt root accepted')
assert h.history(meta(w))==[{'label':'corrupt_guard'}]
print('History retention: world/checkpoint/anchor/UI/recent-write roots retained; old orphan reclaimed; corrupt root prevents deletion: PASS')
