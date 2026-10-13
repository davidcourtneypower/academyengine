"""Synthetic local microbenchmarks, not a claim about FC27 frame rate."""
import sys,os,tempfile,importlib.util,json,copy,time,statistics,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);args=p.parse_args()
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='fc27bench08_')
from academy_manager import read_model as new
from fc27_academy.path_history_store import externalize
spec=importlib.util.spec_from_file_location('old_read_model',Path(args.baseline)/'academy_manager/read_model.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
old.DB_PATH=Path(tempfile.mkdtemp())/'old.sqlite3'
rows=[{'playerid':i,'name':f'Player {i}','ovr':60,'club':'Club','lifecycle':'CLUB','normal_styles':['Technical'],'next_ps':'Inventive','next_ps_pct':40,'roles':[],'observed_this_checkpoint':True} for i in range(5032)]
results={}
for label,module in [('v1.24.07',old),('v1.24.08',new)]:
 module.sync_world('test',{},rows);measure=[]
 for _ in range(5):
  start=time.perf_counter();module.sync_world('test',{},rows);measure.append((time.perf_counter()-start)*1000)
 results[label+'_unchanged_5032_median_ms']=round(statistics.median(measure),2)
entries=[{'checkpoint_id':f'day-{i}','career_date':{'day':i+1,'month':1,'year':2026},'from':i,'to':i+1,'increment':1,'source_attributes':{'dribbling':1},'multiplier':1,'source':'NATIVE_ATTRIBUTE_GROWTH'} for i in range(12)]
w={'players':{str(i):{'engine':{'playstyle_progress_meta':{'Technical':{'history':copy.deepcopy(entries),'last_increment':1}}}} for i in range(5032)}}
results['synthetic_inline_world_bytes']=len(json.dumps(w,separators=(',',':')).encode())
start=time.perf_counter();externalize(w);results['initial_history_migration_ms']=round((time.perf_counter()-start)*1000,2)
results['synthetic_referenced_world_bytes']=len(json.dumps(w,separators=(',',':')).encode())
print(json.dumps(results,indent=2))
