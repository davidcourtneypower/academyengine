from fc27_academy.fsutil import replace_retry
from pathlib import Path
import json, os


def _atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,separators=(',',':'),sort_keys=True),encoding='utf-8')
    replace_retry(tmp,path)


def ingest_receipt_files(root):
    """Move Lua receipts into durable storage inside the same save namespace."""
    root=Path(root); results=[]; saves=root/'saves'
    if not saves.exists(): return results
    for incoming in sorted(saves.glob('*/lua_receipts')):
        durable=incoming.parent/'sync_receipts'; durable.mkdir(parents=True,exist_ok=True)
        for src in sorted(incoming.glob('*.receipt.json')):
            try:
                receipt=json.loads(src.read_text(encoding='utf-8'))
                cid=str(receipt.get('changeset_id') or '').strip()
                if not cid: raise ValueError('missing changeset_id')
                dest=durable/f'{cid}.receipt.json'
                if not dest.exists(): _atomic_json(dest,receipt)
                src.unlink(missing_ok=True)
                results.append((receipt,dest))
            except Exception as exc:
                results.append(({'changeset_id':src.stem},exc))
    return results
