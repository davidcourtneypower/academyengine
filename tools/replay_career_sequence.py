from __future__ import annotations

"""Replay recorded FC27 CHECKPOINT_SNAPSHOT payloads through Academy Engine.

This intentionally runs without FC27 or Live Editor.  It is meant for regression
fixtures captured from real careers so load, advance, rollback and season-change
sequences can be reproduced deterministically outside the game process.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Replay must never touch the user's live Academy Engine database. Paths are
# resolved at import time, so isolate LOCALAPPDATA before importing engine code.
_REPLAY_LOCALAPPDATA = Path(tempfile.mkdtemp(prefix="fc27ae_replay_state_"))
os.environ["LOCALAPPDATA"] = str(_REPLAY_LOCALAPPDATA)

from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService


def _payload(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("kind") == "CHECKPOINT_SNAPSHOT" and isinstance(obj.get("payload"), dict):
        return dict(obj["payload"])
    if isinstance(obj.get("payload"), dict) and "players" in obj["payload"]:
        return dict(obj["payload"])
    if "players" in obj:
        return dict(obj)
    raise ValueError(f"{path}: not a checkpoint snapshot or payload")


def replay(paths: list[Path]) -> list[dict]:
    service = BridgeService(FileBridge())
    results = []
    for index, path in enumerate(paths, 1):
        payload = _payload(path)
        payload.setdefault("runtime_session", "replay-session")
        payload.setdefault("checkpoint_id", f"replay-{index}")
        payload.setdefault("trigger", "REPLAY")
        req = BridgeRequest(f"replay-{index}", "CHECKPOINT_SNAPSHOT", payload)
        result = service.handle(req)
        results.append({"fixture": str(path), "status": result.get("status"), "payload": result.get("payload") or {}})
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay FC27 Academy Engine checkpoint fixtures")
    ap.add_argument("fixtures", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true", help="print full JSON results")
    args = ap.parse_args()
    results = replay(args.fixtures)
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for item in results:
            p = item["payload"]
            print(f"{Path(item['fixture']).name}: {item['status']} storage={p.get('storage_key','-')} players={p.get('player_count','-')} reason={p.get('reason','-')}")
    return 0 if all(x["status"] == "OK" for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
