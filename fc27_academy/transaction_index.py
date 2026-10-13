"""Disposable in-memory index; durable manifests/receipts remain authoritative.

Startup scans everything. Writes update the index immediately; a low-frequency
stat sweep detects external edits, additions and deletions without reparsing
unchanged completed files. Failed reads are retried, never treated as completed.
"""
import json,time
from pathlib import Path

OPEN={'STAGED','STAGED_STATE_HOLD'}
_indexes={}
class ManifestIndex:
    def __init__(self,root):
        self.root=Path(root);self.stamps={};self.pending={};self.by_id={};self.checkpoints={};self.scanned=False;self.last_scan=0
    def update(self,path,obj):
        path=Path(path)
        try:
            st=path.stat();self.stamps[path]=(st.st_mtime_ns,st.st_size)
        except OSError: return
        self.by_id[path.stem]=path
        self.checkpoints[path]=(str(obj.get("save_uid")),str(obj.get("checkpoint_id")),obj.get("changeset_id"))
        if obj.get('status') in OPEN:self.pending[path]=obj
        else:self.pending.pop(path,None)
    def refresh(self):
        now=time.monotonic()
        if self.scanned and now-self.last_scan<60:return
        seen=set()
        for path in (self.root/'saves').glob('*/live_ps_transactions/*.json'):
            seen.add(path)
            try:
                st=path.stat()
                if self.stamps.get(path)==(st.st_mtime_ns,st.st_size):continue
                obj=json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(obj,dict):continue
                self.update(path,obj)
            except (OSError,ValueError):continue
        for path in self.stamps.keys()-seen:
            self.stamps.pop(path,None);self.pending.pop(path,None);self.by_id.pop(path.stem,None);self.checkpoints.pop(path,None)
        self.last_scan=now;self.scanned=True

def index_for(root):
    key=str(Path(root).resolve())
    index=_indexes.setdefault(key,ManifestIndex(Path(key)))
    index.refresh();return index

def note_manifest(path,obj):
    path=Path(path).resolve()
    if path.parent.name!='live_ps_transactions':return
    root=path.parents[3]
    key=str(root)
    index=_indexes.setdefault(key,ManifestIndex(root))
    index.update(path,obj)

def pending_manifests(root,save_dir=None):
    index=index_for(root)
    return [(p,dict(m)) for p,m in sorted(index.pending.items()) if save_dir is None or p.parent==Path(save_dir).resolve()]
