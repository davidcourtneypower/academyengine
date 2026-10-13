"""v1.24.35 regressions: 50 faces per batch for every region; opening the picker never loads
hundreds of faces to reach the current one (it is pinned first instead); the thumbnail cache no
longer deletes thumbnails a long list still uses (blank tiles); Load more stops at the cap."""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
os.environ["FC27AE_SHOW_FACES"] = "1"   # v1.24.37: the face feature is hidden by default
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12435_")
from PIL import Image
from fc27_academy import faces as F
from academy_manager import face_render as R

assert F.PICKER_PAGE == 50
src = (ROOT / "academy_manager/overlay_export.py").read_text(encoding="utf-8")
assert "batch=face_lib.PICKER_PAGE" in src and "view.get('face_page_size')" not in src
print("Batch: 50 faces for every region and window size: PASS")

idx = {"root": "r", "M": {"Ireland": [f"Ireland/{i}.png" for i in range(2400)], "Spain": [f"Spain/{i}.png" for i in range(30)]}, "F": {}, "count": 2430}
w = {"career_uid": "C", "players": {"1": {"game": {"playerid": 1, "birthdate": 1, "nationality": 25, "gender": 0},
                                          "engine": {"face": {"file": "Ireland/1990.png", "region": "Ireland", "gender": "M", "source": "auto", "identity": "1|1|25|M"}}}}}
pg = F.picker_page(w, 1, idx, "", 0, {}, 50)
assert pg["region"] == "Ireland" and pg["shown"] == 50 and len(pg["faces"]) == 51 and pg["faces"][0]["file"] == "Ireland/1990.png" and pg["faces"][0]["current"]
pg = F.picker_page(w, 1, idx, "Ireland", 5000, {}, 50)
assert pg["shown"] == F.MAX_PICKER_FACES == 950 and len(pg["faces"]) == 951            # cap (+ pinned current)
pg = F.picker_page(w, 1, idx, "Spain", 0, {}, 50)
assert pg["shown"] == 30 and len(pg["faces"]) == 30 and not any(f["current"] for f in pg["faces"])
c = (ROOT / "native_overlay/source/academy_overlay.c").read_text(encoding="utf-8")
assert "#define FP_SHOWN_CAP 950" in c and "#define MAX_FACES 1000" in c
print("Opening: one batch with the current face pinned first (no 1000-face loads); Load more stops at 950: PASS")

lib = Path(tempfile.mkdtemp(prefix="faces_"))
img = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); img.paste((210, 160, 130, 255), (16, 16, 48, 48))
for i in range(600): img.save(lib / f"{i}.png")
paths = [R.overlay_face_bmp(lib / f"{i}.png", "#081b2d") for i in range(600)]
assert all(p and p.is_file() for p in paths), sum(1 for p in paths if not (p and p.is_file()))   # was: only the newest 400 survived
# the clean-up only removes least-recently-used thumbnails beyond the limit, never recent ones
R.CACHE_KEEP = 100
R._prune(force=True)
assert all(p.is_file() for p in paths)                                                         # all used within the last 30 minutes
old = time.time() - 7200
for p in paths[:550]: os.utime(p, (old, old))
R._prune(force=True)
left = [p for p in paths if p.is_file()]
assert len(left) == 100 and all(p in left for p in paths[550:])
print("Thumbnail cache: a long list keeps all its thumbnails; clean-up removes only old, unused ones: PASS")
print("FC27 Academy Engine v1.24.35 regression: PASS")
