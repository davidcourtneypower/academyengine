"""Developer aid: turn a draw log from tests/native/snapshot_main.c (+ gdi_log.c) into a PNG.

    python tools/render_overlay_snapshot.py draw.log out.png 1600 900
Rectangles, text and bitmaps are drawn approximately (DejaVu instead of Bahnschrift) so the
overlay layout can be checked without Windows.
"""
import sys
from PIL import Image, ImageDraw, ImageFont
log, out, W, H = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
im = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(im)
fonts = {}
def font(px, bold):
    k = (px, bold)
    if k not in fonts:
        try: fonts[k] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed%s.ttf" % ("-Bold" if bold else ""), max(8, px - 2))
        except Exception: fonts[k] = ImageFont.load_default()
    return fonts[k]
def rgb(h):  # COLORREF 0x00BBGGRR
    v = int(h, 16); return (v & 255, (v >> 8) & 255, (v >> 16) & 255)
base = im; clips = []          # IntersectClipRect / RestoreDC: draw on a layer, paste back inside the clip
for line in open(log, encoding="utf-8", errors="replace"):
    t = line.rstrip("\n")
    if t.startswith("C "):
        c = tuple(int(v) for v in t.split()[1:]); clips.append((im, c)); im = im.copy(); d = ImageDraw.Draw(im); continue
    if t == "U":
        if clips:
            outer, c = clips.pop(); outer.paste(im.crop(c), c[:2]); im = outer; d = ImageDraw.Draw(im)
        continue
    if t.startswith("R "):
        _, l, tp, r, b, fill, pen = t.split(" ")
        d.rectangle((int(l), int(tp), int(r) - 1, int(b) - 1), fill=rgb(fill), outline=rgb(pen))
    elif t.startswith("T "):
        head, text = t.split("\t", 1); p = head.split(" ")
        l, tp, r, b, col, fl, fh, wt = int(p[1]), int(p[2]), int(p[3]), int(p[4]), p[5], int(p[6]), int(p[7]), int(p[8])
        f = font(fh, wt >= 600); w = d.textlength(text, font=f)
        while w > r - l and len(text) > 2: text = text[:-2] + "…"; w = d.textlength(text, font=f)
        x = l + (r - l - w) / 2 if fl & 1 else (r - w if fl & 2 else l)
        d.text((x, tp), text, fill=rgb(col), font=f)
    elif t.startswith("B "):
        head, path = t.split("\t", 1); p = head.split(" ")
        try: im.paste(Image.open(path).convert("RGB").resize((int(p[3]), int(p[4]))), (int(p[1]), int(p[2])))
        except Exception as e: d.rectangle((int(p[1]), int(p[2]), int(p[1]) + 96, int(p[2]) + 96), outline=(255, 0, 0))
im.save(out)
