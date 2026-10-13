"""Semantic regressions for all five optimisations. No game or user state needed."""
import os,sys,tempfile,json,copy,time,sqlite3
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27ae_perf08_')
from academy_manager import read_model as rm
from fc27_academy import path_history_store as hs
from fc27_academy.transaction_index import index_for,note_manifest,pending_manifests,_indexes
from fc27_academy.live_playstyle_writer import reconcile_durable_receipts
from fc27_academy.paths import BRIDGE_ROOT,ACADEMY_STATE_ROOT
from fc27_academy.transaction_store import create_checkpoint,checkpoint_for_date
from fc27_academy.save_restore_points import restore_for_date
from fc27_academy.save_context import _clone_storage
from academy_manager import overlay_revision as rev
from academy_manager import overlay_export as export

rows=[dict(playerid=i,name=f'Player {i}',club='Club',ovr=60,normal_styles=[],plus_styles=[],roles=[],lifecycle='CLUB',observed_this_checkpoint=True,next_ps='Technical',next_ps_pct=20) for i in range(1,5033)]
w={'players':{},'career':{}}
t=time.perf_counter();a=rm.sync_world('test',w,rows);initial=time.perf_counter()-t
assert a['rows_written']==5032
with rm._connect() as con:
 con.execute('CREATE TABLE write_audit (pid INTEGER)')
 con.execute('CREATE TRIGGER count_player_insert AFTER INSERT ON players BEGIN INSERT INTO write_audit VALUES(new.playerid); END;')
t=time.perf_counter();a=rm.sync_world('test',w,rows);unchanged=time.perf_counter()-t
assert a['rows_written']==0
with rm._connect() as con:assert con.execute('SELECT COUNT(*) FROM write_audit').fetchone()[0]==0
rows[17]['ovr']=61;rows=rows[:-1];a=rm.sync_world('test',w,rows);assert (a['rows_written'],a['rows_deleted'])==(1,1)
assert rm.get_player('test',18)['ovr']==61 and rm.get_player('test',5032) is None
assert rm.sync_world('other',w,rows)['rows_written']==5031
assert rm.sync_world('test',w,[])['rows_deleted']==5031
print(f'Incremental SQL: 5032 initial writes, zero unchanged, one changed + one removed; {initial*1000:.1f}ms initial / {unchanged*1000:.1f}ms unchanged')

root=Path(tempfile.mkdtemp());folder=root/'saves/s/live_ps_transactions';folder.mkdir(parents=True)
for i in range(300):
 p=folder/f'old{i}.json';p.write_text(json.dumps(dict(status='COMMITTED',changeset_id=p.stem,save_uid='s',checkpoint_id=p.stem)))
p=folder/'pending.json';obj=dict(status='STAGED',changeset_id='pending',save_uid='s',checkpoint_id='day');p.write_text(json.dumps(obj))
idx=index_for(root);assert len(idx.stamps)==301 and len(idx.pending)==1
with patch.object(Path,'read_text',side_effect=AssertionError('idle manifest reread')):
 for _ in range(30):assert reconcile_durable_receipts(root)==[]
p.write_text(json.dumps({**obj,'status':'COMMITTED'}));note_manifest(p,{**obj,'status':'COMMITTED'});assert not pending_manifests(root)
p.write_text(json.dumps(obj));_indexes.clear();assert len(pending_manifests(root))==1
p.unlink();idx=index_for(root);idx.last_scan=0;assert not pending_manifests(root)
print('Transaction index: idle scans avoided; writer updates, restart recovery and external deletion detected')

entry={'checkpoint_id':'old','from':0,'to':5,'increment':5}
world={'save_uid':'source','storage_key':'source','career_uid':'career','career':{'date':{'day':1,'month':1,'year':2026}},'players':{'1':{'engine':{'playstyle_progress_meta':{'Technical':{'history':[entry],'last_increment':5}}}}}}
old=copy.deepcopy(world);hs.externalize(world);meta=world['players']['1']['engine']['playstyle_progress_meta']['Technical'];assert 'history' not in meta
assert hs.hydrate_world(world)==old
create_checkpoint('source',world=world,events={},trigger='TEST',request_id='old')
assert checkpoint_for_date('source',{'day':1,'month':1,'year':2026})['world']==world
future=copy.deepcopy(world);fm=future['players']['1']['engine']['playstyle_progress_meta']['Technical'];hs.editable_history(fm).append({**entry,'checkpoint_id':'new'});hs.externalize(future)
assert hs.history(meta)==[entry] and len(hs.history(fm))==2
result=restore_for_date('source','child',{'day':1,'month':1,'year':2026});assert result['status']=='RESTORED'
restored=json.loads((ACADEMY_STATE_ROOT/'saves/child/generated_world.json').read_text());assert hs.history(restored['players']['1']['engine']['playstyle_progress_meta']['Technical'])==[entry]
_clone_storage(BRIDGE_ROOT,ACADEMY_STATE_ROOT,'child','grandchild');clone=json.loads((ACADEMY_STATE_ROOT/'saves/grandchild/generated_world.json').read_text());assert hs.hydrate_world(clone)==hs.hydrate_world(restored)
try:hs.history({'history_ref':'missing'})
except RuntimeError:pass
else:raise AssertionError('Missing reference silently ignored')
# An unsuccessful history commit cannot remove inline evidence.
with patch.object(hs,'_connect',side_effect=OSError('disk full')):
 failed=copy.deepcopy(old)
 try:hs.externalize(failed)
 except OSError:pass
 assert failed==old
print('History: inline migration, immutable old/new, checkpoint rewind, Save As, missing/corrupt guard and failed-write retention')

life={'state':'READY','storage_key':'child','career_uid':'career','generation':1}
a=rev.revision(life,123,{'state':'IDLE','finished_at':1});assert a==rev.revision({**life,'generation':2,'updated_at':9},123,{'state':'IDLE','finished_at':999})
for change in ({'state':'DETACHED'},{'storage_key':'grandchild'},{'request_id':'new'},{'career_date':{'day':2}}):assert a!=rev.revision({**life,**change},123,{'state':'IDLE'})
assert a!=rev.revision(life,0,{'state':'IDLE'})
for path in [rev.BRIDGE_ROOT/'overlay_view.json',rev.BRIDGE_ROOT/'active_context.lua',rev.USER_ROOT/'manager_settings.json',rev.career_settings_path('child'),rev.EVENTS_ROOT/'child/events.json']:
 before=rev.revision(life,123);path.parent.mkdir(parents=True,exist_ok=True);path.write_text('changed');assert rev.revision(life,123)!=before
export.STATE_FILE.parent.mkdir(parents=True,exist_ok=True);export.STATE_FILE.write_text('existing')
with patch.object(export,'tx_lifecycle',return_value=life),patch.object(export,'game_pid',return_value=123),patch.object(export,'_publish_overlay_state') as publish:
 export._last_publication_revision=None
 assert export.publish_overlay_state() is True
 assert export.publish_overlay_state() is False
 assert publish.call_count==1
 export.VIEW_FILE.write_text('selected')
 assert export.publish_overlay_state() is True
 export.STATE_FILE.unlink();assert export.publish_overlay_state() is True
 export._last_publication_revision=None;publish.side_effect=RuntimeError('failed publication')
 try:export.publish_overlay_state()
 except RuntimeError:pass
 assert export._last_publication_revision is None
print('Overlay: stable idle skipped; selection/settings/events/save/lifecycle revisions and missing output retrigger; failed publish retries')
print('v1.24.08 performance regressions: PASS')
