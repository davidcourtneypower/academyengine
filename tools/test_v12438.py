"""v1.24.38 regressions: cleanup build before a public release.

1. Diagnostic-only checkpoint calculations (dry-run preview, top-progress list, season
   "mass event" check) are gone; a checkpoint still reconciles and stages writes.
2. Lua crash tracing opens only around loads, save switches and exits (two minutes), not on
   every save; the v1.24.20 squad diagnostic is removed.
3. bridge.log rotates during a session; overlay_host.log and bridge_startup.log are capped.
4. Debug / stress-test mode is hidden unless FC27AE_DEBUG=1: treated as off, absent from the
   settings page, cannot be switched on, and a career that had it on returns to normal ranges.
5. The public release zip holds only run-time files and works on its own.
"""
from __future__ import annotations
import copy, json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12438_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("FC27AE_DEBUG", None)

# ---- 1. diagnostic calculations removed ------------------------------------------------------
for mod in ("dry_run_changeset", "development_observability", "season_progression_audit"):
    assert not (ROOT / "fc27_academy" / f"{mod}.py").exists(), mod
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
base = json.loads((ROOT / "tests/fixtures/01_load.json").read_text())
base = base.get("payload") or base
svc = BridgeService(FileBridge())
r = svc.handle(BridgeRequest("a", "CHECKPOINT_SNAPSHOT", dict(base, runtime_session="RS", day_epoch=0, checkpoint_id="c0", trigger="CAREER_SETTLED_BASELINE")))
assert r["status"] == "OK", r
grown = json.loads((ROOT / "tests/fixtures/02_day_growth.json").read_text())
grown = grown.get("payload") or grown
r = svc.handle(BridgeRequest("b", "CHECKPOINT_SNAPSHOT", dict(grown, runtime_session="RS", day_epoch=1, checkpoint_id="c1", trigger="DAY_SETTLED")))
p = r["payload"]
assert r["status"] == "OK" and "audits_ms" in p["timings"], p.get("timings")
for gone in ("dry_run", "development_observability", "season_progression"):
    assert gone not in p, gone
for kept in ("playstyle_plan", "playstyle_lifetime", "ps_acquisition", "live_write"):
    assert kept in p, kept
src = (ROOT / "run_bridge_service.py").read_text(encoding="utf-8")
assert "OBSERVE_TOP" not in src
print("Checkpoint: diagnostic-only calculations gone, reconcile and staging unchanged: PASS")

# ---- 2. Lua tracing ------------------------------------------------------------------------------
from lupa import LuaRuntime
prelude = r'''
logs={};sent={};responded={};uid='SAVE1';in_cm=true;NOW=1000000
os.time=function() return NOW end
os.getenv=function() return '/test' end
require=function() end
Log=function(m) logs[#logs+1]=m end
GetSaveUID=function() return uid end
IsInCM=function() return in_cm end
dofile=function(p) return {career_uid=uid,runtime_session=_G.TEST_SESSION,branch_id='b',storage_key=uid..'__b',writes_held=false} end
io.open=function(path,mode)
 if string.find(path,'engine_enabled.lease',1,true) then return {read=function() return tostring(NOW) end,close=function() end} end
 if string.find(path,'responses',1,true) then if responded[path] then return {close=function() end} end return nil end
 if string.find(path,'pending_sync',1,true) then return nil end
 return {write=function() end,flush=function() end,close=function() end,read=function() return '' end}
end
LE={db={GetTable=function() return {} end}}
AddEventHandler=function(name,fn) handler=fn end
'''
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(prelude)
rt = (ROOT / "integration/lua/FC27_Academy_Engine_Runtime.lua").read_text(encoding="utf-8")
assert "SQUAD_DIAG" not in rt and "squad_diag" not in rt
assert "if b==28 then trace_window" not in rt and "local TRACE_SECONDS=120" in rt
rt = rt.replace("local function OnCareerEvent(a,b,...)", '''
_G.TEST_SESSION=SESSION
emit_snapshot=function(trigger)
 seq=seq+1; sent[#sent+1]=trigger; inflight_id="req"..seq; inflight_since=os.time(); coalesced_days=0
 return true,inflight_id,1,0,0,"MOCK"
end
function respond_last() if inflight_id then responded[RESPONSES.."\\\\"..inflight_id..".json"]=true end end
local function OnCareerEvent(a,b,...)''', 1)
lua.execute(rt)
def logs(): t = lua.eval("logs"); return [t[i] for i in range(1, len(t) + 1)]
def ev(e): lua.execute(f"handler(nil,{e})")
def traced(): return sum(1 for l in logs() if l.startswith("FC27AE_EVENT "))
ev(26); lua.execute("respond_last()")                   # first load (a save switch) opens the window
ev(68)
assert traced() > 0
lua.execute("NOW=NOW+121")                              # two minutes later the window has closed
n = traced(); ev(15); lua.execute("respond_last()"); ev(28); lua.execute("respond_last()"); ev(15)
assert traced() == n, "a save opened the event trace again"
ev(29); ev(68)                                          # a load boundary opens the window again
assert traced() > n
lua.execute("NOW=NOW+60"); m = traced(); ev(68)
assert traced() == m + 1, "still inside the two-minute window after a load"
print("Lua: event trace only around loads/switches/exits, two minutes; saves no longer trace; squad diagnostic gone: PASS")

# ---- 3. logs bounded ------------------------------------------------------------------------------
import run_bridge_service as rbs
logdir = Path(tempfile.mkdtemp())
rbs._LOG_FILE = logdir / "bridge.log"
rbs._LOG_FILE.write_bytes(b"x" * 5_000_001)
rbs._log_lines = 0
for i in range(rbs._LOG_CHECK_EVERY):
    rbs.emit(f"line {i}")
assert (logdir / "bridge.log.1").exists() and rbs._LOG_FILE.stat().st_size < 100_000, sorted(os.listdir(logdir))
from fc27_academy.fsutil import cap_log
big = logdir / "overlay_host.log"; big.write_bytes(b"y" * 2_000_000); cap_log(big)
assert (logdir / "overlay_host.log.1").exists() and not big.exists()
for f in ("academy_manager/overlay_host.py", "academy_manager/engine_controller.py"):
    assert "cap_log(" in (ROOT / f).read_text(encoding="utf-8"), f
print("Logs: bridge.log rotates during a session at 5 MB; host and startup logs capped at 2 MB: PASS")

# ---- 4. debug mode hidden -------------------------------------------------------------------------
from fc27_academy import runtime_config as rc
from fc27_academy.runtime_config import career_settings_path
from fc27_academy.settings import Settings
from fc27_academy.transaction_store import lifecycle
from academy_manager import overlay_export as ex
from academy_manager.live_data import active_world
ex.detect_game = lambda *a, **k: True; ex.game_pid = lambda *a, **k: 4242
key = active_world()["storage_key"]
cfg = Settings(path=career_settings_path(key))
cfg.data.setdefault("production", {})["debug_stress_mode"] = True
cfg.data.setdefault("development", {})["playstyle_progression_speed"] = 50.0
cfg.data["production"]["max_total_changes_per_checkpoint"] = 300
cfg.save()
rc.load_runtime_settings(force=True)
assert rc.debug_stress_mode() is False and rc.normal_progress_multiplier() == 10.0 and rc.max_total_changes_per_checkpoint() == 64
assert ex.publish_overlay_state({})
st = ex.STATE_FILE.read_text(encoding="utf-8")
assert "GROUP|debug|" not in st and "|debug_stress_mode|" not in st
d = json.loads(career_settings_path(key).read_text(encoding="utf-8"))
assert d["production"]["debug_stress_mode"] is False and d["development"]["playstyle_progression_speed"] == 10.0, d
assert d["production"]["max_total_changes_per_checkpoint"] <= 64, d["production"]
seq = [0]
def command(body):
    seq[0] += 1; g = int(lifecycle()["generation"])
    (ex.BRIDGE_ROOT / f"overlay_cmd_{seq[0]:010d}_{seq[0]:06d}.txt").write_text(f"GEN|{g}\n{body}\n")
    ex.process_overlay_command(); ex.publish_overlay_state({})
def debug_flag(): return json.loads(career_settings_path(key).read_text(encoding="utf-8"))["production"]["debug_stress_mode"]
command("SET|career|production|debug_stress_mode|true")
assert debug_flag() is False, "debug mode switched on while hidden"
os.environ["FC27AE_DEBUG"] = "1"                         # control: the same command works for developers
command("SET|career|production|debug_stress_mode|true")
assert debug_flag() is True and "GROUP|debug|" in ex.STATE_FILE.read_text(encoding="utf-8")
os.environ.pop("FC27AE_DEBUG")
ex._last_publication_revision = None; ex.publish_overlay_state({})
assert debug_flag() is False and "GROUP|debug|" not in ex.STATE_FILE.read_text(encoding="utf-8")
print("Debug mode: hidden and treated as off; cannot be switched on; an existing career returns to normal ranges; FC27AE_DEBUG=1 shows it: PASS")

# ---- 5. public release zip ---------------------------------------------------------------------------
out = Path(tempfile.mkdtemp())
res = subprocess.run([sys.executable, str(ROOT / "tools/make_release.py"), str(out), "--name", "rel"], capture_output=True, text=True, cwd=ROOT)
assert res.returncode == 0, res.stdout + res.stderr
names = zipfile.ZipFile(out / "rel.zip").namelist()
assert names and all(n.startswith("FC27_Academy_Engine/") for n in names)
rel = [n.split("/", 1)[1] for n in names]
for bad in ("tools/", "tests/", "docs/"):
    assert not any(n.startswith(bad) for n in rel), bad
assert not any("__pycache__" in n or n.endswith((".pyc", ".pdb")) for n in rel)
assert not any(n.endswith(".md") and n != "README.md" for n in rel)
for need in ("FC27 Academy Engine.bat", "run_manager.py", "native_overlay/AcademyOverlayHost.exe", "integration/lua/FC27_Academy_Engine_Runtime.lua"):
    assert need in rel, need
zipfile.ZipFile(out / "rel.zip").extractall(out)
tree = out / "FC27_Academy_Engine"
smoke = r'''
import json, os, sys, tempfile
sys.path.insert(0, sys.argv[1]); os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from academy_manager import overlay_export as ex
import academy_manager.launcher, run_bridge_service
ex.detect_game = lambda *a, **k: True; ex.game_pid = lambda *a, **k: 1
base = json.loads(open(sys.argv[2]).read()); base = base.get("payload") or base
r = BridgeService(FileBridge()).handle(BridgeRequest("s", "CHECKPOINT_SNAPSHOT", dict(base, runtime_session="S", day_epoch=0, checkpoint_id="s0", trigger="CAREER_SETTLED_BASELINE")))
assert r["status"] == "OK", r
assert ex.publish_overlay_state({})
assert sys.modules["fc27_academy"].__file__.startswith(sys.argv[1])
print("SMOKE_OK")
'''
res = subprocess.run([sys.executable, "-I", "-c", smoke, str(tree), str(ROOT / "tests/fixtures/01_load.json")],
                     capture_output=True, text=True, cwd=str(tree), env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
assert "SMOKE_OK" in res.stdout, res.stdout[-2000:] + res.stderr[-3000:]
print(f"Release zip: {len(rel)} run-time files only (no tests, tools, docs, caches or debug symbols); runs on its own: PASS")
print("FC27 Academy Engine v1.24.38 regression: PASS")
