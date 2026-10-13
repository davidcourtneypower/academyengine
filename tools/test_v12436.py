"""v1.24.36 regressions: PlayStyle decline with age and retirement handling.

Decline: personal start age 30-40 by peak-OVR band; losses need sustained low key attributes
(below 70 and well below the player's peak), a grace period and 60 days between losses;
PlayStyle+ drops to the normal PlayStyle first; at-cap losses shrink the lifetime cap
(1/1 -> 0/0); lost PlayStyles are not re-earned; both switches off by default.
Retirement: older players FC27 no longer holds are hidden everywhere and their faces freed.
The whole flow runs through the real bridge, writer, receipts, events, exporter and overlay C."""
import collections, copy, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["FC27AE_SHOW_FACES"] = "1"   # v1.24.37: the face feature is hidden by default
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12436_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from fc27_academy import playstyle_decline as D
from fc27_academy.staged_sync import Change, validate_change, StageError
from fc27_academy.playstyle_sync import PLAYSTYLE1

# --- start age distribution ---------------------------------------------------------------------
want = {"REGULAR": [8, 10, 12, 14, 14, 14, 12, 8, 5, 2, 1], "STRONG": [6, 8, 10, 11, 13, 13, 12, 11, 8, 5, 3], "ELITE": [4, 5, 7, 8, 10, 11, 12, 11, 10, 9, 13]}
for name, lo, factor in D.BANDS:
    c = collections.Counter(D.start_age_for(i / 20000, factor) for i in range(20000))
    got = [round(100 * c[a] / 20000) for a in range(30, 41)]
    assert all(abs(g - w) <= 1 for g, w in zip(got, want[name])), (name, got)
assert D.band_for(86)[0] == "ELITE" and D.band_for(82)[0] == "STRONG" and D.band_for(70)[0] == "REGULAR"
print("Start age: 30-40, rising chance each birthday, elite players later (matches the agreed table): PASS")

# --- write checks ------------------------------------------------------------------------------------
R, Q = PLAYSTYLE1["Rapid"], PLAYSTYLE1["Quick Step"]
assert validate_change(Change(460001, "trait1", R | Q, Q, "PLAYSTYLE_LOSS", "t"))
assert validate_change(Change(460001, "icontrait1", R, 0, "PLAYSTYLE_PLUS_LOSS", "t"))
for bad in (Change(460001, "trait1", Q, Q | R, "PLAYSTYLE_LOSS", "adds"), Change(460001, "trait1", Q, 0 if False else Q ^ R, "PLAYSTYLE_LOSS", "absent bit"),
            Change(460001, "trait1", R | Q, 0, "PLAYSTYLE_LOSS", "two bits"), Change(460001, "icontrait1", R, 0, "PLAYSTYLE_LOSS", "wrong field"),
            Change(460001, "trait1", R, 0, "PLAYSTYLE_PLUS_LOSS", "wrong field"), Change(460001, "trait2", 64, 0, "PLAYSTYLE_LOSS", "not a PlayStyle bit"),
            Change(100, "trait1", R, 0, "PLAYSTYLE_LOSS", "real player")):
    try: validate_change(bad); raise AssertionError(bad.reason)
    except StageError: pass
# additive acquisitions still cannot remove anything
try: validate_change(Change(460001, "trait1", R | Q, Q, "PLAYSTYLE", "t")); raise AssertionError
except StageError: pass
print("Write checks: a loss clears exactly one present, known PlayStyle bit on a generated player; nothing else: PASS")

# --- model rules (unit) --------------------------------------------------------------------------------
def player(age, pace, trait1=R | Q, icon1=0, ovr=80, cap=None):
    g = {"playerid": 460010, "birthdate": 1, "nationality": 14, "age": age, "overallrating": ovr, "preferredposition1": 27,
         "trait1": trait1, "icontrait1": icon1, "trait2": 0, "icontrait2": 0,
         "attributes": {"acceleration": pace, "sprintspeed": pace, "agility": pace, "balance": 70}}
    p = {"playerid": 460010, "game": g, "engine": {}, "observed_this_checkpoint": True, "lifecycle": "CLUB"}
    if cap is not None: p["engine"]["playstyle_lifetime_normal_cap"] = cap
    return p
def step(p, days=7, n=1, on=(True, True), credit=True):
    r = None
    for _ in range(n): r = D.update_player(p, seed="S", credit=credit, days=days, normal_on=on[0], plus_on=on[1])
    return r
p = player(29, 90); step(p); assert not p["engine"]["decline"].get("active")           # under 30: nothing
p = player(40, 90); step(p, n=3)                                                          # peak 90
p["game"]["attributes"].update(acceleration=60, sprintspeed=60, agility=60)
step(p, n=1); assert p["engine"]["decline"]["active"] and p["engine"]["decline"]["progress"]["Rapid"] > 0
step(p, n=8); assert p["engine"]["decline"]["ready"] == {"style": "Quick Step", "kind": "LOSS"} or p["engine"]["decline"]["ready"]["kind"] == "LOSS"
# PlayStyle+ goes first
p = player(40, 90, icon1=R); step(p, n=2); p["game"]["attributes"].update(acceleration=60, sprintspeed=60, agility=60); step(p, n=10)
assert p["engine"]["decline"]["ready"] == {"style": "Rapid", "kind": "PLUS_DOWNGRADE"}
# grace: no loss before 3 credited checkpoints even at 100%
p = player(40, 90); step(p); p["game"]["attributes"].update(acceleration=40, sprintspeed=40, agility=40)
p["engine"]["decline"]["active_checkpoints"] = 0; p["engine"]["decline"]["progress"] = {"Rapid": 100.0}
step(p, n=1); assert p["engine"]["decline"]["ready"] is None
step(p, n=2); assert p["engine"]["decline"]["ready"] is not None
# elite still above the floor keeps it; recovery eases progress back
p = player(40, 96); step(p); p["game"]["attributes"].update(acceleration=86, sprintspeed=86, agility=86); step(p, n=20)
assert p["engine"]["decline"]["progress"].get("Rapid", 0) == 0 and p["engine"]["decline"]["ready"] is None
p = player(31, 90); p["engine"]["decline"] = {"start_age": 30, "peaks": {"acceleration": 90, "sprintspeed": 90, "agility": 90}, "progress": {"Rapid": 60.0}}
step(p, n=1); assert 0 < p["engine"]["decline"]["progress"]["Rapid"] < 60
# switches: off freezes progress; PlayStyle+ off skips the PlayStyle+ style
p = player(40, 60); p["engine"]["decline"] = {"start_age": 30, "active": True, "active_checkpoints": 9, "peaks": {"acceleration": 90, "sprintspeed": 90, "agility": 90}, "progress": {"Rapid": 50.0}}
step(p, n=5, on=(False, False)); assert p["engine"]["decline"]["progress"]["Rapid"] == 50.0
p = player(40, 60, icon1=R); p["engine"]["decline"] = {"start_age": 30, "active": True, "active_checkpoints": 9, "days_since_loss": 999, "peaks": {"acceleration": 90, "sprintspeed": 90, "agility": 90}}
step(p, n=10, on=(True, False)); assert "Rapid" not in p["engine"]["decline"]["status"] and p["engine"]["decline"]["ready"]["style"] == "Quick Step"
# development checkpoints only (no credit -> no progress)
p = player(40, 60); p["engine"]["decline"] = {"start_age": 30, "peaks": {"acceleration": 90, "sprintspeed": 90, "agility": 90}}
step(p, n=5, credit=False); assert not p["engine"]["decline"].get("progress", {}).get("Rapid")
# deterministic start age per identity
a = player(30, 80); b = player(30, 80); step(a); step(b); assert a["engine"]["decline"]["start_age"] == b["engine"]["decline"]["start_age"]
# 60 days between losses for one player
p = player(40, 60); p["engine"]["decline"] = {"start_age": 30, "active": True, "active_checkpoints": 9, "days_since_loss": 0,
                                               "peaks": {"acceleration": 90, "sprintspeed": 90, "agility": 90}, "progress": {"Rapid": 100.0, "Quick Step": 100.0}}
step(p, days=7, n=8); assert p["engine"]["decline"]["ready"] is None          # 56 days
step(p, days=7, n=1); assert p["engine"]["decline"]["ready"] is not None      # 63 days
print("Model: under 30 nothing; grace; PlayStyle+ first; elite above the floor keeps it; recovery; switches; credited checkpoints only: PASS")

# cap rules
for owned, cap, after in ((4, 4, 3), (1, 1, 0), (2, 4, 4), (5, 4, 4)):
    q = player(35, 60, cap=cap); D.apply_committed_loss(q, "LOSS", "Rapid", normal_before=owned)
    assert q["engine"]["playstyle_lifetime_normal_cap"] == after, (owned, cap, q["engine"]["playstyle_lifetime_normal_cap"])
q = player(35, 60, icon1=R, cap=4); q["engine"]["playstyle_plus_lifetime_eligible"] = True
D.apply_committed_loss(q, "PLUS_DOWNGRADE", "Rapid", normal_before=2)
assert q["engine"]["playstyle_plus_lifetime_eligible"] is False and q["engine"]["playstyle_lifetime_normal_cap"] == 4
from fc27_academy.playstyle_lifetime import normal_cap, ensure_policy
q = player(35, 60, trait1=0, cap=0); q["engine"]["playstyle_lifetime_policy_version"] = ensure_policy(player(20, 60))["normal_cap"] and None
q["engine"]["playstyle_lifetime_policy_version"] = __import__("fc27_academy.playstyle_lifetime", fromlist=["POLICY_VERSION"]).POLICY_VERSION
assert normal_cap(q) == 0
print("Lifetime cap: at cap 4/4 -> 3/3 and 1/1 -> 0/0 (0 stays 0); below cap 2/4 -> 1/4; downgrade ends PlayStyle+ eligibility: PASS")

# --- end to end through the bridge -----------------------------------------------------------------
from fc27_academy.file_bridge import FileBridge, BridgeRequest
from fc27_academy.bridge_service import BridgeService
from fc27_academy import live_playstyle_writer as writer
from fc27_academy.paths import BRIDGE_ROOT
from fc27_academy.event_engine import record_commit, load_events
from fc27_academy.runtime_config import career_settings_path, load_runtime_settings
from fc27_academy.settings import Settings
from fc27_academy.world_bootstrap_store import WorldBootstrapStore
from fc27_academy.paths import ACADEMY_STATE_ROOT
from academy_manager.live_data import active_world, player_rows

obj = json.loads((ROOT / "tests/fixtures/01_load.json").read_text()); base = obj.get("payload") or obj
def mk(pid, age, pace, trait1=0, icon1=0, ovr=80):
    p = copy.deepcopy(base["players"][0]); p.update(playerid=pid, name=f"P{pid}", age=age, overallrating=ovr, trait1=trait1, icontrait1=icon1, birthdate=700000 + pid)
    p["attributes"] = dict(p["attributes"], acceleration=pace, sprintspeed=pace, agility=pace)
    return p
players = {460001: mk(460001, 36, 88, R | Q, R, ovr=82), 460002: mk(460002, 34, 70), 460003: mk(460003, 22, 70), 460004: mk(460004, 37, 75, R, 0, ovr=75)}
svc = BridgeService(FileBridge()); day = [0]; n = [0]
def checkpoint(trigger="DAY_SETTLED", days=7):
    n[0] += 1; day[0] += days
    import datetime as _dt
    _d = _dt.date(2030, 7, 1) + _dt.timedelta(days=day[0])                        # career date moves with the days played
    career = dict(base.get("career") or {}, date={"year": _d.year, "month": _d.month, "day": _d.day})
    r = svc.handle(BridgeRequest(f"r{n[0]}", "CHECKPOINT_SNAPSHOT", dict(base, players=list(copy.deepcopy(players).values()), runtime_session="RS",
                                                                        day_epoch=day[0], checkpoint_id=f"cp{n[0]}", trigger=trigger, career=career)))
    assert r["status"] == "OK", r
checkpoint("SCREEN_LOADED_BASELINE", 0)
key = active_world()["storage_key"]
wpath = WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(key)
def edit_world(fn):
    w = json.loads(wpath.read_text()); fn(w); wpath.write_text(json.dumps(w))
cfg = Settings(path=career_settings_path(key))
cfg.update_many([("production", "newgen_enrichment_per_checkpoint", 0)]); cfg.save(); load_runtime_settings(force=True)
# switches off by default: nothing happens even for an old, slow player
players[460004]["attributes"].update(acceleration=55, sprintspeed=55, agility=55)
for _ in range(4): checkpoint()
assert not (active_world()["players"]["460004"]["engine"].get("decline") or {}).get("active")
print("Default: both decline switches off -> no decline: PASS")

cfg = Settings(path=career_settings_path(key)); cfg.update_many([("decline", "playstyle_loss_enabled", True), ("decline", "playstyle_plus_loss_enabled", True)]); cfg.save()
load_runtime_settings(force=True)
edit_world(lambda w: w["players"]["460004"]["engine"].update(playstyle_lifetime_normal_cap=1))     # 1/1 -> 0/0 case
def commit_pending():
    sr = BRIDGE_ROOT / "saves" / key; pend = sr / "pending_sync.lua"
    if not pend.exists(): return None
    ms = [json.loads(x.read_text()) for x in sorted((sr / "live_ps_transactions").glob("*.json"))]
    m = next((x for x in ms if x.get("status") == "STAGED"), None)
    if not m: return None
    pend.unlink()
    res = writer.apply_receipt(BRIDGE_ROOT, {"changeset_id": m["changeset_id"], "status": "APPLIED", "reason": "COMMITTED"})
    assert res["status"] == "COMMITTED", res
    record_commit(key, res)
    for e in m["entries"]: players[e["playerid"]][e["field"]] = e["proposed"]
    return m
order = []
for i in range(70):
    pace = max(60, 88 - i)
    players[460001]["attributes"].update(acceleration=pace, sprintspeed=pace, agility=pace)
    checkpoint()
    m = commit_pending()
    if m: order += [(e["playerid"], e["kind"], e["style"], e["field"]) for e in m["entries"]]
w1 = [x for x in order if x[0] == 460001]
assert w1[0][1:] == ("PLUS_DOWNGRADE", "Rapid", "icontrait1")
assert [x[1:3] for x in w1[1:]] == [("PLAYSTYLE_LOSS", "Quick Step"), ("PLAYSTYLE_LOSS", "Rapid")] or [x[1:3] for x in w1[1:]] == [("PLAYSTYLE_LOSS", "Rapid"), ("PLAYSTYLE_LOSS", "Quick Step")]
assert players[460001]["trait1"] == 0 and players[460001]["icontrait1"] == 0
pw = active_world()["players"]["460001"]; d = pw["engine"]["decline"]
assert [x["kind"] for x in d["lost"]] == ["PLUS_DOWNGRADE", "LOSS", "LOSS"] and pw["engine"]["playstyle_plus_lifetime_eligible"] is False
p4 = active_world()["players"]["460004"]
assert [x[1:3] for x in order if x[0] == 460004] == [("PLAYSTYLE_LOSS", "Rapid")] and p4["engine"]["playstyle_lifetime_normal_cap"] == 0
ev = [(e["type"], e["playerid"], e.get("value")) for e in load_events(key) if e["type"] in ("PLAYSTYLE_LOST", "PLAYSTYLE_PLUS_DOWNGRADED")]
assert ("PLAYSTYLE_PLUS_DOWNGRADED", 460001, "Rapid+ → Rapid") in ev and ("PLAYSTYLE_LOST", 460004, "Rapid") in ev and len(ev) == 4
print("Career: Rapid+ -> Rapid -> lost, Quick Step lost, spaced apart; 1/1 player goes to 0/0; events recorded: PASS")
# re-earning blocked while pace stays low: no progress builds for the lost styles
ns = pw["engine"].get("playstyle_progress") or {}
assert float(ns.get("Rapid", 0) or 0) == 0 and float(ns.get("Quick Step", 0) or 0) == 0
assert D.reacquire_blocked(pw, "Rapid")
pw["game"]["attributes"].update(acceleration=85, sprintspeed=85); assert not D.reacquire_blocked(pw, "Rapid")
print("Lost PlayStyles are not re-earned unless the attributes clearly recover: PASS")

# --- exporter + overlay ------------------------------------------------------------------------------------
from academy_manager import overlay_export as ex
from fc27_academy.transaction_store import lifecycle
ex.detect_game = lambda *a, **k: True; ex.game_pid = lambda *a, **k: 4242
assert ex.publish_overlay_state({})
seq = [0]
def command(body):
    seq[0] += 1; g = int(lifecycle()["generation"])
    (ex.BRIDGE_ROOT / f"overlay_cmd_{seq[0]:010d}_{seq[0]:06d}.txt").write_text(f"GEN|{g}\n{body}\n")
    ex.process_overlay_command(); assert ex.publish_overlay_state({})
    return ex.STATE_FILE.read_text(encoding="utf-8")
st = command("SELECT|460001")
rows = re.findall(r"^DECLINE\|460001\|([^|]*)\|[^|]*\|[^|]*\|(\d)\|", st, re.M)
assert ("Rapid+", "3") in rows and ("Rapid", "3") in rows and ("Quick Step", "3") in rows, rows
assert re.search(r"^SELECTED_DECLINE_SINCE=3\d$", st, re.M)
assert "GROUP|decline|AGEING & PLAYSTYLE DECLINE|" in st and "|playstyle_loss_enabled|PlayStyle loss with age|bool|True|" in st
assert "|playstyle_plus_loss_enabled|" in st and "|decline_speed|Decline speed|float|1.0|" in st and "|playstyle_lost|PlayStyle loss popup|bool|" in st
print("Exporter: decline rows (lost / downgraded), decline start age, decline settings section: PASS")
from academy_manager import read_model
assert any(r["playerid"] == 460001 for r in read_model.query_players({"storage_key": key, "state": "Declining"}, limit=50)[0])
assert not any(r["playerid"] == 460003 for r in read_model.query_players({"storage_key": key, "state": "Declining"}, limit=50)[0])
print("Players list: 'Declining' status filter: PASS")

# --- retirement -------------------------------------------------------------------------------------------
from fc27_academy import faces as F
gone = {k: players.pop(k) for k in (460002, 460003)}
for _ in range(2): checkpoint()
assert not active_world()["players"]["460002"].get("retired")                    # needs 3 missing checkpoints
checkpoint()
w = active_world()
assert w["players"]["460002"].get("retired") and not w["players"]["460003"].get("retired")
assert all(r["playerid"] != 460002 for r in player_rows(w)) and any(r["playerid"] == 460003 for r in player_rows(w))
st = command("SELECT|460001")
assert not re.search(r"^PLAYERS_BEGIN[\s\S]*\|P460002\|", st, re.M)
# a partial snapshot (most players missing) is not trusted
from fc27_academy.world_bootstrap_store import update_retirements
dd = {"players": {str(i): {"last_seen_age": 35} for i in range(10)}}
assert update_retirements(dd, {"0"}, set(map(str, range(10))), "x")["trusted"] is False and not any(p.get("missing_checkpoints") for p in dd["players"].values())
# seen again -> visible again
players[460002] = gone[460002]; checkpoint()
assert not active_world()["players"]["460002"].get("retired")
players.pop(460002)
for _ in range(3): checkpoint()
assert active_world()["players"]["460002"].get("retired")
# events of retired players are hidden; their face returns to the pool
ws = active_world()
ws["players"]["460002"]["engine"]["face"] = {"file": "Ireland/x.png", "region": "Ireland", "gender": "M", "source": "auto", "identity": F.identity_of(ws["players"]["460002"]["game"])}
idx = {"root": "r", "M": {"Ireland": ["Ireland/x.png"]}, "F": {}, "count": 1}
F.assign_faces(ws, {"face_enabled": True, "face_library_path": "r"}, idx)
assert ws["players"]["460001"]["engine"]["face"]["file"] == "Ireland/x.png"            # the only face, freed by the retired player
from fc27_academy.event_engine import append_event
append_event(key, {"type": "PLAYSTYLE_GAINED", "title": "PlayStyle Acquired", "playerid": 460002, "player_name": "P460002", "value": "Rapid", "career_date": {}})
assert all(e["playerid"] != 460002 for e in ex._merged_normalized_events(key, active_world()))
# long-retired records are trimmed after two seasons
edit_world(lambda w: w.update(season_epoch=int(w.get("season_epoch", 0) or 0) + 2))
checkpoint()
r2 = active_world()["players"]["460002"]
assert r2["retired"].get("trimmed") and r2["history"] == [] and set(r2["game"]) <= set(__import__("fc27_academy.world_bootstrap_store", fromlist=["x"])._RETIRED_KEEP_GAME)
print("Retirement: 33+ missing 3 checkpoints -> hidden (rows, events), face freed, partial snapshots ignored, reappearance restores, trimmed after 2 seasons: PASS")

# --- native overlay ---------------------------------------------------------------------------------------
c_src = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert '"At lifetime PlayStyle cap","Declining"}' in c_src and "if(g_filter_popup==2)return 6;" in c_src
cc = shutil.which("clang") or shutil.which("gcc")
if not cc:
    print("Overlay native check: SKIPPED (no C compiler)")
else:
    dtmp = Path(tempfile.mkdtemp())
    (dtmp / "overlay_llp64.c").write_text(c_src.replace("typedef unsigned long DWORD;", "typedef unsigned int DWORD;").replace("typedef long LONG;", "typedef int LONG;"), encoding="utf-8")
    for f in ("gdi_log.c", "snapshot_main.c"): shutil.copy(ROOT / "tests/native" / f, dtmp / f)
    flags = ["-fms-extensions", "-fdeclspec", "-w", "-O0"] if "clang" in cc else ["-fms-extensions", "-w", "-O0"]
    first = subprocess.run([cc, *flags, "-o", str(dtmp / "snap"), str(dtmp / "snapshot_main.c"), str(dtmp / "gdi_log.c")], capture_output=True, text=True)
    miss = sorted(set(re.findall(r"undefined reference to [`']([A-Za-z_]\w*)'", first.stderr)))
    (dtmp / "stubs.c").write_text("".join(f"long long {m}(){{return 0;}}\n" for m in miss))
    subprocess.run([cc, *flags, "-o", str(dtmp / "snap"), str(dtmp / "snapshot_main.c"), str(dtmp / "gdi_log.c"), str(dtmp / "stubs.c")], check=True)
    st = command("SELECT|460001"); (dtmp / "dev.txt").write_text(st, encoding="utf-8")
    subprocess.run([str(dtmp / "snap"), str(dtmp / "dev.txt"), "460001", "0", "1"], check=True, capture_output=True, env=dict(os.environ, GDI_LOG=str(dtmp / "dev.log")))
    log = (dtmp / "dev.log").read_text(encoding="utf-8")
    assert "\tPLAYSTYLE DECLINE" in log and "Decline phase active since age 3" in log and "\tLost" in log and "\tDropped to Rapid at age" in log
    st = command("SELECT|460003"); (dtmp / "young.txt").write_text(st, encoding="utf-8")
    subprocess.run([str(dtmp / "snap"), str(dtmp / "young.txt"), "460003", "0", "1"], check=True, capture_output=True, env=dict(os.environ, GDI_LOG=str(dtmp / "young.log")))
    assert "PLAYSTYLE DECLINE" not in (dtmp / "young.log").read_text(encoding="utf-8") and "PLAYSTYLE PATHS" in (dtmp / "young.log").read_text(encoding="utf-8")
    print("Overlay (real C): PLAYSTYLE DECLINE section only once decline is active; lost/downgraded rows shown: PASS")
# --- receipts: a loss must not disturb Role++ cooldowns (found in review before release) ----------
from fc27_academy.paths import ACADEMY_STATE_ROOT
from fc27_academy.world_bootstrap_store import WorldBootstrapStore
from fc27_academy.live_playstyle_writer import apply_receipt, save_root
from fc27_academy.playstyle_sync import PLAYSTYLE1
from fc27_academy.transaction_index import note_manifest
uid = "CAREER_RC"; R = PLAYSTYLE1["Rapid"]
wp = WorldBootstrapStore(ACADEMY_STATE_ROOT).path_for(uid); wp.parent.mkdir(parents=True, exist_ok=True)
def rc_player(pid, **eng):
    return {"playerid": pid, "observed_this_checkpoint": True, "lifecycle": "CLUB",
            "game": {"playerid": pid, "age": 34, "trait1": R, "trait2": 0, "icontrait1": 0, "icontrait2": 0, "role1": 10, "role2": 0, "role3": 0, "role4": 0, "role5": 0},
            "engine": {"playstyle_lifetime_normal_cap": 1, **eng}, "history": []}
world = {"save_uid": uid, "storage_key": uid, "players": {"460010": rc_player(460010), "460011": rc_player(460011, role_acquisition_cooldown_days_remaining=45)}}
wp.write_text(json.dumps(world))
root = Path(tempfile.mkdtemp()); sr = save_root(root, uid); (sr / "live_ps_transactions").mkdir(parents=True)
def run(cid, entries):
    m = {"changeset_id": cid, "status": "STAGED", "save_uid": uid, "entries": entries}
    mp = sr / "live_ps_transactions" / f"{cid}.json"; mp.write_text(json.dumps(m)); note_manifest(mp, m)   # as stage_bundle does
    r = apply_receipt(root, {"changeset_id": cid, "status": "APPLIED", "reason": "COMMITTED"}); assert r.get("status") != "MANIFEST_NOT_FOUND", r
    return json.loads(wp.read_text())
w = run("cs_role", [{"kind": "ROLE_UPGRADE", "family": "ROLE", "playerid": 460010, "role": "Playmaker++", "field": "role1", "expected": 10, "proposed": 11, "cooldown_days": 90, "progress_before": 100.0}])
e = w["players"]["460010"]["engine"]
assert e.get("role_acquisition_cooldown_days_remaining") == 90 and e.get("role_acquisition_last_receipt") == "cs_role", e
w = run("cs_loss", [{"kind": "PLAYSTYLE_LOSS", "family": "PLAYSTYLE_LOSS", "playerid": 460011, "style": "Rapid", "bit": R, "field": "trait1", "expected": R, "proposed": 0, "cooldown_days": 0, "normal_before": 1, "progress_before": 100.0}])
e = w["players"]["460011"]["engine"]
assert e.get("role_acquisition_cooldown_days_remaining") == 45 and "role_acquisition_last_receipt" not in e, e   # loss leaves Role++ cooldown alone
assert e["playstyle_lifetime_normal_cap"] == 0 and w["players"]["460011"]["game"]["trait1"] == 0      # 1/1 -> 0/0
print("Receipts: Role++ still starts its cooldown; a PlayStyle loss never touches Role++ cooldowns: PASS")
# --- fixes from the independent review ---------------------------------------------------------------------
# a ready loss never survives the switches being turned off (and the writer re-checks the switch)
p = player(40, 90); step(p, n=3); p["game"]["attributes"].update(acceleration=60, sprintspeed=60, agility=60); step(p, n=12)
assert p["engine"]["decline"]["ready"]
step(p, n=1, on=(False, False)); assert p["engine"]["decline"]["ready"] is None
w_src = (ROOT / "fc27_academy/live_playstyle_writer.py").read_text(encoding="utf-8")
assert "if not _switch.get(str(ready.get('kind'))): continue" in w_src
# goalkeeper PlayStyles are judged on goalkeeper attributes (GK snapshots carry no pace)
for st in ("Rush Out", "Far Reach", "Deflector", "Footwork", "Cross Claimer", "Far Throw", "Quick Reflexes"):
    assert all(a.startswith("gk") for a in D.loss_attributes(st)), st
gk = {"attributes": {"gkreflexes": 60, "gkdiving": 62, "gkhandling": 61, "gkpositioning": 63, "gkkicking": 64}}
assert D.evaluate_style({"peaks": {"gkreflexes": 85, "gkdiving": 84, "gkhandling": 80, "gkpositioning": 80, "gkkicking": 80}}, gk, "Rush Out")["declining"]
# receipt replay does not record a loss twice
pl = player(36, 60, trait1=R, cap=1); before = D.apply_committed_loss(pl, "LOSS", "Rapid", normal_before=1, changeset_id="cs1")
again = D.apply_committed_loss(pl, "LOSS", "Rapid", normal_before=1, changeset_id="cs1")
assert len(pl["engine"]["decline"]["lost"]) == 1 and again.get("replayed") and pl["engine"]["playstyle_lifetime_normal_cap"] == 0
# a PlayStyle+ removed without a normal replacement (PlayStyles full) is not re-earned either
pl = player(36, 60, trait1=0, icon1=R); D.apply_committed_loss(pl, "PLUS_DOWNGRADE", "Rapid", normal_before=7, added_normal=False, kept_normal=False, changeset_id="cs2")
assert D.reacquire_blocked(pl, "Rapid")
pl = player(36, 60, trait1=R, icon1=R); D.apply_committed_loss(pl, "PLUS_DOWNGRADE", "Rapid", normal_before=1, kept_normal=True, changeset_id="cs3")
assert not D.reacquire_blocked(pl, "Rapid")                          # had both: normal Rapid simply stays
# retirement: consecutive partial snapshots cannot lower the bar; an empty snapshot never counts
dd = {"players": {str(i): {"last_seen_age": 35} for i in range(10)}}
assert update_retirements(dd, set(map(str, range(10))), set(map(str, range(10))), "a")["trusted"]
for _ in range(4):
    assert update_retirements(dd, {"0"}, {"0"}, "b")["trusted"] is False
assert update_retirements({"players": {"1": {"last_seen_age": 35}}}, set(), set(), "c")["trusted"] is False
assert not any(x.get("retired") for x in dd["players"].values())
# missing must also span a week of career time (saves/reloads on one day do not retire anyone)
dd = {"players": {"9": {"last_seen_age": 35}}, "retirement_reference_count": 1}
for _ in range(5): update_retirements(dd, {"x"}, {"x"}, "d", {"date": {"year": 2031, "month": 1, "day": 3}})
assert not dd["players"]["9"].get("retired")
update_retirements(dd, {"x"}, {"x"}, "e", {"date": {"year": 2031, "month": 1, "day": 10}})
assert dd["players"]["9"].get("retired")
# a trimmed record keeps lifetime limits, PlayStyle+ eligibility, DNA, face and decline history
from fc27_academy.world_bootstrap_store import _retired_engine_keep
kept = _retired_engine_keep({"playstyle_lifetime_policy_version": 3, "playstyle_lifetime_normal_cap": 1, "playstyle_plus_lifetime_eligible": False,
                             "football_dna": {"x": 1}, "face": {"file": "a"}, "playstyle_progress": {"Rapid": 50},
                             "decline": {"start_age": 33, "lost": [1], "status": {}, "progress": {}, "ready": None, "peaks": {"a": 1}}})
assert kept["playstyle_lifetime_policy_version"] == 3 and kept["playstyle_plus_lifetime_eligible"] is False and kept["football_dna"]
assert "playstyle_progress" not in kept and set(kept["decline"]) == {"start_age", "lost", "peaks"}
wb_src = (ROOT / "fc27_academy/world_bootstrap_store.py").read_text(encoding="utf-8")
assert "if isinstance(_f,dict) and _f.get('source')!='user': existing['engine'].pop('face',None)" in wb_src   # face re-picked on return
# shrinking-but-trusted snapshots cannot ratchet the bar down; no career date -> no retirement
dd = {"players": {str(i): {"last_seen_age": 35} for i in range(1000)}}
update_retirements(dd, set(map(str, range(1000))), set(), "r0", {"date": {"year": 2031, "month": 1, "day": 1}})
for k, n in enumerate((500, 250, 125)):
    update_retirements(dd, set(map(str, range(n))), set(), f"r{k+1}", {"date": {"year": 2031, "month": 1, "day": 10 + 9 * k}})
assert dd["retirement_reference_count"] == 1000 and sum(1 for x in dd["players"].values() if x.get("retired")) == 0
dd = {"players": {"9": {"last_seen_age": 35}}, "retirement_reference_count": 1}
for _ in range(6): update_retirements(dd, {"x"}, {"x"}, "n")
assert not dd["players"]["9"].get("retired")
# a goalkeeper's passing PlayStyle declines on distribution; ones with no GK equivalent do not
gkg = {"preferredposition1": 0, "attributes": {"gkkicking": 60}}
assert D.evaluate_style({"peaks": {"gkkicking": 80}}, gkg, "Long Ball Pass")["declining"]
assert not D.evaluate_style({"peaks": {}}, gkg, "Long Throw")["declining"]
print("Review fixes: stale ready loss cleared when switched off; GK PlayStyles use GK attributes; replay-safe; full-PlayStyles downgrade not re-earned;"
      " retirement needs trusted snapshots over a week; trimmed records keep lifetime limits: PASS")
print("FC27 Academy Engine v1.24.36 regression: PASS")
