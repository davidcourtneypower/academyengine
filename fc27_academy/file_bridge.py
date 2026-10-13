"""Crash-safe file bridge between FC27 Live Editor Lua and Academy Engine.

Protocol uses atomic request JSON files plus atomic JSON response files.
The game-side bridge only emits snapshots/events; Python owns DNA/evolution decisions.
No FC27 database write is performed by this module.
"""
from __future__ import annotations
from fc27_academy.fsutil import replace_retry
from dataclasses import dataclass
from pathlib import Path
import json, os, time

PROTOCOL_VERSION = 1
from .paths import BRIDGE_ROOT


def default_bridge_dir() -> Path:
    return BRIDGE_ROOT


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    replace_retry(tmp, path)


@dataclass(frozen=True)
class BridgeRequest:
    request_id: str
    kind: str
    payload: dict
    protocol: int = PROTOCOL_VERSION

    @classmethod
    def parse(cls, line: str) -> "BridgeRequest":
        obj = json.loads(line)
        if int(obj.get("protocol", -1)) != PROTOCOL_VERSION:
            raise ValueError("unsupported bridge protocol")
        rid = str(obj.get("request_id", "")).strip()
        kind = str(obj.get("kind", "")).strip()
        payload = obj.get("payload", {})
        if not rid or not kind or not isinstance(payload, dict):
            raise ValueError("invalid bridge request")
        return cls(rid, kind, payload)


class FileBridge:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else default_bridge_dir()
        self.responses = self.root / "responses"
        self.request_files = self.root / "request_files"
        self.state = self.root / "bridge_state.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.responses.mkdir(parents=True, exist_ok=True)
        self.request_files.mkdir(parents=True, exist_ok=True)

    def poll(self) -> list[BridgeRequest]:
        out: list[BridgeRequest] = []
        # Snapshots are streamed by Lua to a temp file and
        # atomically renamed here. This avoids constructing/retaining a multi-MB
        # JSON line inside the embedded Live Editor Lua VM. Files remain durable
        # until a matching response exists.
        for path in sorted(self.request_files.glob("*.request.json")):
            try:
                obj=json.loads(path.read_text(encoding="utf-8"))
                req=BridgeRequest.parse(json.dumps(obj,separators=(",",":")))
                if (self.responses / f"{req.request_id}.json").exists():
                    path.unlink(missing_ok=True)
                    continue
                out.append(req)
            except (OSError, ValueError, json.JSONDecodeError):
                # Atomic rename means a valid file should be complete. Keep an
                # unreadable file for diagnosis rather than deleting evidence.
                continue
        return out

    def respond(self, request_id: str, *, status: str, payload: dict | None = None) -> Path:
        target = self.responses / f"{request_id}.json"
        _atomic_json(target, {"protocol":PROTOCOL_VERSION,"request_id":request_id,
                              "status":status,"payload":payload or {},"written_at":time.time()})
        return target

    def publish_state(self, **state) -> Path:
        _atomic_json(self.state, {"protocol":PROTOCOL_VERSION, **state})
        return self.state
