from __future__ import annotations

"""Offline v1.24 architecture regression test.

Runs a tiny synthetic career through load -> genuine development -> rewind ->
reload-newer using an isolated LOCALAPPDATA.  No FC27/Live Editor process is
needed and the user's persistent Academy Engine data cannot be touched.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Engine paths are resolved at import time, so isolate them first.
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v124_selftest_state_")

from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.world_bootstrap_store import WorldBootstrapStore
from fc27_academy.paths import ACADEMY_STATE_ROOT
from fc27_academy.transaction_store import set_lifecycle, detach, lifecycle
from academy_manager.overlay_export import COMMAND_FILE, process_overlay_command

FIX = ROOT / "tests" / "fixtures"
SEQUENCE = [
    FIX / "01_load.json",
    FIX / "02_day_growth.json",
    FIX / "03_rewind.json",
    FIX / "04_reload_newer.json",
]


def payload(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    return dict(obj.get("payload") or obj)


def top_ps_progress(result: dict) -> float:
    """Highest PlayStyle progress in the world the checkpoint just persisted (call right after it)."""
    key = (result.get("payload") or {}).get("storage_key")
    world = json.loads(WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(key).read_text(encoding="utf-8"))
    vals = [float(v or 0.0) for p in (world.get("players") or {}).values()
            for v in ((p.get("engine") or {}).get("playstyle_progress") or {}).values()]
    return max(vals, default=0.0)


def main() -> int:
    bridge = FileBridge()
    service = BridgeService(bridge)
    results = []
    progress = []
    for i, path in enumerate(SEQUENCE, 1):
        p = payload(path)
        p.setdefault("runtime_session", "v124-self-test")
        p.setdefault("checkpoint_id", f"self-test-{i}")
        req = BridgeRequest(f"self-test-{i}", "CHECKPOINT_SNAPSHOT", p)
        r = service.handle(req)
        if r.get("status") != "OK":
            raise AssertionError(f"{path.name}: expected OK, got {r.get('status')} {r.get('payload')}")
        results.append(r)
        progress.append(top_ps_progress(r))

    first, grown, rewound, resumed = results
    first_progress, grown_progress, rewind_progress, resumed_progress = progress

    assert first_progress == 0.0, first_progress
    assert grown_progress > 0.0, grown_progress
    assert rewind_progress == 0.0, rewind_progress
    assert abs(resumed_progress - grown_progress) < 0.001, (resumed_progress, grown_progress)

    p1 = first["payload"]
    p2 = grown["payload"]
    p3 = rewound["payload"]
    p4 = resumed["payload"]
    assert p1.get("storage_key") == p2.get("storage_key")
    assert p3.get("storage_key") != p2.get("storage_key")
    assert (p3.get("exact_save_anchor") or {}).get("status") == "RESTORED"
    assert (p4.get("exact_save_anchor") or {}).get("status") == "RESTORED"

    # Verify persisted player state agrees with the reported development evidence.
    world = json.loads(WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(p4["storage_key"]).read_text(encoding="utf-8"))
    players = world.get("players") or {}
    assert players, "resumed branch has no persisted players"

    # UI commands are immutable-generation-bound. A delayed click from an older
    # read model must not be able to mutate a newer READY generation.
    set_lifecycle("READY", runtime_session="self-test", career_uid="TESTSAVE", storage_key=p4["storage_key"], generation=7)
    COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMMAND_FILE.write_text("GEN|6\nACTION|clear_logs\n", encoding="utf-8")
    assert process_overlay_command() is False, "stale generation command was accepted"
    COMMAND_FILE.write_text("GEN|7\nACTION|clear_logs\n", encoding="utf-8")
    assert process_overlay_command() is True, "current generation command was rejected"
    detach("self-test detach")
    assert lifecycle().get("generation") == 0 and lifecycle().get("career_uid") == "", "detach did not invalidate live generation"

    # Exact-save rollback: Academy progression earned after an unsaved advance must
    # not survive reloading the exact same FC27 save, even if the game date did not
    # change. The initial baseline creates an exact save anchor.
    base = payload(FIX / "01_load.json")
    base["save_uid"] = "TESTSAVE_EXACT"
    base["runtime_session"] = "v124-exact-test"
    base["checkpoint_id"] = "exact-baseline"
    base["trigger"] = "CAREER_SETTLED_BASELINE"
    rb = service.handle(BridgeRequest("exact-baseline", "CHECKPOINT_SNAPSHOT", base))
    assert rb.get("status") == "OK", rb
    grown_same = payload(FIX / "02_day_growth.json")
    grown_same["save_uid"] = "TESTSAVE_EXACT"
    grown_same["runtime_session"] = "v124-exact-test"
    grown_same["checkpoint_id"] = "exact-unsaved-growth"
    grown_same["trigger"] = "DAY_SETTLED"
    grown_same.setdefault("career", {})["date"] = dict((base.get("career") or {}).get("date") or {})
    rg = service.handle(BridgeRequest("exact-growth", "CHECKPOINT_SNAPSHOT", grown_same))
    assert rg.get("status") == "OK", rg
    assert top_ps_progress(rg) > 0.0, top_ps_progress(rg)
    reload_same = dict(base)
    reload_same["checkpoint_id"] = "exact-reload"
    reload_same["trigger"] = "CAREER_SETTLED_BASELINE"
    rr = service.handle(BridgeRequest("exact-reload", "CHECKPOINT_SNAPSHOT", reload_same))
    assert rr.get("status") == "OK", rr
    assert (rr.get("payload") or {}).get("exact_save_anchor",{}).get("status") == "RESTORED", (rr.get("payload") or {}).get("exact_save_anchor")
    assert top_ps_progress(rr) == 0.0, top_ps_progress(rr)

    print("FC27 Academy Engine v1.0.7 self-test: PASS")
    print(f"  initial progress : {first_progress:.2f}%")
    print(f"  developed        : {grown_progress:.2f}%")
    print(f"  rewind restored  : {rewind_progress:.2f}%")
    print(f"  newer resumed    : {resumed_progress:.2f}%")
    print(f"  active branch    : {p4.get('storage_key')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
