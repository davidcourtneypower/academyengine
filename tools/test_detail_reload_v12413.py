"""v1.24.13: re-opening the same player must never leave the overlay on
"Loading player details" (match-day report, 08-10-2026).

The bridge reuses a read generation when the rebuilt payload is identical, so Back +
re-open of the same player published a byte-identical overlay_state.txt and the overlay,
which skips identical files, never re-read it. Each processed command now changes the
file (COMMAND_SEQ) without creating extra generations. The two files published here by
the real exporter are then fed to the real overlay C code (built natively).
"""
import os, re, shutil, subprocess, sys, tempfile, time, json, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_detail_")
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy.transaction_store import lifecycle
from academy_manager import overlay_export as ex
ex.detect_game = lambda *a, **k: True
ex.game_pid = lambda *a, **k: 4242

obj = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = obj.get("payload") or obj
players = []
for i in range(5):
    p = copy.deepcopy(base["players"][0]); p["playerid"] = 460000 + i; p["name"] = f"P {i}"; players.append(p)
svc = BridgeService(FileBridge())
r = svc.handle(BridgeRequest("a", "CHECKPOINT_SNAPSHOT", dict(base, players=players, runtime_session="RS", day_epoch=0, trigger="SCREEN_LOADED_BASELINE")))
assert r["status"] == "OK", r
ex.publish_overlay_state({})
assert lifecycle()["state"] == "READY"

seq = [0]
def command(body):
    seq[0] += 1; g = int(lifecycle()["generation"])
    (ex.BRIDGE_ROOT / f"overlay_cmd_{seq[0]:010d}_{seq[0]:06d}.txt").write_text(f"GEN|{g}\n{body}\n")

PID = 460002
command(f"SELECT|{PID}"); assert ex.process_overlay_command(); assert ex.publish_overlay_state({})
first = ex.STATE_FILE.read_bytes(); gen1 = lifecycle()["generation"]
# Back, then the same player again before the bridge loop publishes in between.
command("SELECT|0"); command(f"SELECT|{PID}"); assert ex.process_overlay_command(); assert ex.publish_overlay_state({})
second = ex.STATE_FILE.read_bytes(); gen2 = lifecycle()["generation"]
strip = lambda b: re.sub(rb"COMMAND_SEQ=[^\n]*\n", b"", b)
assert gen1 == gen2, (gen1, gen2)                   # no extra generations
assert strip(first) == strip(second)                 # same data ...
assert first != second                               # ... but the file changes
# Same player clicked again with nothing in between: still a new file.
command(f"SELECT|{PID}"); assert ex.process_overlay_command(); assert ex.publish_overlay_state({})
assert ex.STATE_FILE.read_bytes() != second
print("Exporter: re-opening the same player republishes a changed file without new generations: PASS")

cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Overlay native check: SKIPPED (no C compiler)"); sys.exit(0)
d = Path(tempfile.mkdtemp())
(d / "first.txt").write_bytes(first); (d / "second.txt").write_bytes(second)
src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
src = src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;")
(d / "overlay_llp64.c").write_text(src, encoding="utf-8")
shutil.copy(ROOT / "tests/native/detail_reload_harness.c", d / "harness.c")
flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
first_build = subprocess.run([cc, *flags, "-o", str(d / "h"), str(d / "harness.c")], capture_output=True, text=True)
missing = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first_build.stderr)))
(d / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in missing))
subprocess.run([cc, *flags, "-o", str(d / "h"), str(d / "harness.c"), str(d / "stubs.c")], check=True)
def run(a, b):
    return subprocess.run([str(d / "h"), str(d / a), str(d / b), str(PID)], capture_output=True, text=True)
ok = run("first.txt", "second.txt")
print(ok.stdout.strip().splitlines()[0])
assert ok.returncode == 0 and "PASS" in ok.stdout, ok.stdout
# Control: the pre-fix behaviour (identical republish) reproduces the stuck screen.
bad = run("first.txt", "first.txt")
assert bad.returncode != 0 and "STUCK" in bad.stdout, bad.stdout
print("Overlay (real C, native): changed file shows the player; identical file reproduces the stuck screen: PASS")
