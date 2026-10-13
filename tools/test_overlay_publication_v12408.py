"""Real exporter + isolated bridge, mocking only the game process and icon downloads."""
import os,sys,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27overlay08_')
from fc27_academy.file_bridge import FileBridge,BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle,set_lifecycle
from academy_manager import overlay_export as ex
from fc27_academy import path_history_store as hs
from fc27_academy.paths import ACADEMY_STATE_ROOT
service=BridgeService(FileBridge())
for i,fn in enumerate(['01_load.json','02_day_growth.json']):
 obj=json.loads((ROOT/'tests/fixtures'/fn).read_text());p=obj.get('payload') or obj
 p['runtime_session']='overlaytest';p['checkpoint_id']=str(i)
 result=service.handle(BridgeRequest('overlay'+str(i),'CHECKPOINT_SNAPSHOT',p));assert result['status']=='OK'
key=result['payload']['storage_key'];wp=ACADEMY_STATE_ROOT/'saves'/key/'generated_world.json'
world=json.loads(wp.read_text());pid=int(next(iter(world['players'])))
meta=world['players'][str(pid)]['engine']['playstyle_progress_meta'];target=next(k for k,v in meta.items() if v.get('history_ref'))
act={'state':'IDLE'}
with patch.object(ex,'detect_game',return_value=True),patch.object(ex,'game_pid',return_value=123):
 ex._last_publication_revision=None
 assert ex.publish_overlay_state(act)
 assert lifecycle()['state']=='READY'
 # Initial promotion changes the lifecycle input once; allow that settling publish.
 ex.publish_overlay_state(act)
 first=ex.STATE_FILE.stat().st_mtime_ns
 for _ in range(10):assert not ex.publish_overlay_state(act)
 assert ex.STATE_FILE.stat().st_mtime_ns==first
 view=ex._load_view(key);view['selected_pid']=pid;ex._save_view(view)
 with patch.object(hs,'history',side_effect=AssertionError('collapsed history was read')):
  assert ex.publish_overlay_state(act)
 assert 'PATH_HISTORY_BEGIN\nPATH_HISTORY_END' in ex.STATE_FILE.read_text()
 # Real generation-bound native command expands one path and loads only it.
 ex.COMMAND_FILE.write_text(f"GEN|{lifecycle()['generation']}\nVIEW|history_path|NORMAL:{target}\n")
 assert ex.process_overlay_command()
 with patch.object(hs,'history',wraps=hs.history) as history:
  assert ex.publish_overlay_state(act);assert history.call_count==1
 payload=ex.STATE_FILE.read_text();section=payload.split('PATH_HISTORY_BEGIN\n')[1].split('PATH_HISTORY_END')[0]
 assert section and all(line.startswith(f'NORMAL|{pid}|{target}|') for line in section.splitlines())
 # Clock expiry still triggers a publish despite unchanged data.
 ex._publication_deadline=0;assert ex.publish_overlay_state(act)
 # Detach, then no game, both invalidate a previously stable generation.
 set_lifecycle('DETACHED',detail='test',generation=0);assert ex.publish_overlay_state(act)
 with patch.object(ex,'detect_game',return_value=False),patch.object(ex,'game_pid',return_value=0):
  assert ex.publish_overlay_state(act);assert 'GAME_RUNNING=0' in ex.STATE_FILE.read_text()
print('Real exporter: stable idle leaves file unchanged; collapsed history unread; generation-bound expansion loads one path; expiry/detach/game-exit refresh: PASS')
