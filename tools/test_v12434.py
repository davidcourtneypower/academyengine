"""v1.24.34 regression: face assignment stays fast even when no folder name is recognised
(region weights are memoised per nationality/gender/library instead of rebuilt per player)."""
import os, random, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["FC27AE_SHOW_FACES"] = "1"   # v1.24.37: the face feature is hidden by default
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12434_")
from fc27_academy import faces as F, face_regions as FR
random.seed(1)
for label, names in (("unrecognised folder names", [f"Region{i}" for i in range(60)]), ("real region names", list(FR.FALLBACKS)[:60])):
    idx = {"root": label, "M": {n: [f"{n}/f{j}.png" for j in range(250)] for n in names},
           "F": {n: [f"WF/{n}/f{j}.png" for j in range(100)] for n in names[:20]}, "count": 17000}
    w = {"career_uid": "C", "players": {}}
    for i in range(2000):
        w["players"][str(460000 + i)] = {"game": {"playerid": 460000 + i, "birthdate": 150000 + i, "nationality": random.randint(1, 215), "gender": 1 if i % 10 == 0 else 0}, "engine": {}}
    t = time.perf_counter(); r = F.assign_faces(w, {"face_enabled": True, "face_library_path": "x"}, idx); first = time.perf_counter() - t
    t = time.perf_counter(); F.assign_faces(w, {"face_enabled": True, "face_library_path": "x"}, idx); later = time.perf_counter() - t
    assert r["assigned"] == 2000 and first < 2.0 and later < 0.5, (label, first, later)   # was ~13 s for unrecognised names
    print(f"{label}: 2000 players {first*1000:.0f} ms first time, {later*1000:.0f} ms per later checkpoint: PASS")
# memo must not leak between libraries: same nationality, different folders
a = {"root": "a", "M": {"Ireland": ["Ireland/1.png"]}, "F": {}, "count": 1}
b = {"root": "b", "M": {"Spain": ["Spain/1.png"]}, "F": {}, "count": 1}
assert F.region_weights(25, "M", a)[0][0] == "Ireland" and F.region_weights(25, "M", b)[0][0] == "Spain"
print("Memoised weights are per library: PASS")
print("FC27 Academy Engine v1.24.34 regression: PASS")
