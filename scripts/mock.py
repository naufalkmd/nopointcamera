"""Local placement mock: board + the screen's fixed layers roughly drawn on top (not the real page)."""
import json
import os
from PIL import Image, ImageDraw, ImageChops
OBJ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") + "/"
K = 2
board = Image.open(OBJ + "np-board.png").convert("RGBA")
W, H = 390 * K, 844 * K
im = board.crop((20, 20, 20 + W, 20 + H))
tint = Image.new("RGB", im.size, (184, 242, 58))
im = Image.blend(im, ImageChops.overlay(im.convert("RGB"), tint).convert("RGBA"), 0.4)
d = ImageDraw.Draw(im)
def R(x0, y0, x1, y1, **kw):
    d.rounded_rectangle([x0 * K, y0 * K, x1 * K, y1 * K], **kw)
R(16, 6, 374, 414, radius=42 * K, fill=(0, 0, 0, 255))
R(63, 60, 327, 390, radius=8, fill=(90, 120, 150, 255))
R(120, 405, 270, 497, radius=4, fill=(238, 232, 218, 255))
pod = Image.new("RGBA", (154 * K, 74 * K), (0, 0, 0, 0))
ImageDraw.Draw(pod).rounded_rectangle([0, 0, 154 * K - 1, 74 * K - 1], radius=37 * K, fill=(190, 255, 70, 56), outline=(225, 255, 140, 230), width=4)
pod = pod.rotate(35, expand=True, resample=Image.BICUBIC)
im.alpha_composite(pod, (int(289 * K - pod.width / 2), int(555 * K - pod.height / 2)))
def put(name, x, y, w):
    sp = Image.open(OBJ + "parts/" + name + ".png").convert("RGBA").resize((int(w * K), int(w * K)), Image.LANCZOS)
    im.alpha_composite(sp, (int(x * K), int(y * K)))
put("c-dpad", 33, 503, 124); put("gb-button", 221, 543, 70); put("gb-button", 287, 497, 70)
put("gb-pill", 118, 658, 64); put("gb-pill", 183, 658, 64)
d.ellipse([252 * K, 688 * K, 360 * K, 796 * K], fill=(8, 18, 10, 110), outline=(220, 255, 130, 255), width=6)
for (x, y, w, h, c) in [(-6, 238, 60, 76, (255, 210, 30)), (336, 92, 52, 64, (107, 227, 107)), (6, 394, 72, 42, (200, 207, 219)),
                        (330, 292, 64, 64, (247, 244, 238)), (12, 652, 62, 72, (255, 210, 30)), (18, 756, 58, 58, (21, 21, 21))]:
    R(x, y, x + w, y + h, radius=16, fill=c + (255,), outline=(255, 255, 255, 255), width=6)
man = json.load(open(OBJ + "parts/manifest.json"))
for it in man:
    if it.get("overlay"):
        sp = Image.open(OBJ + "parts/" + it["key"] + ".png").convert("RGBA")
        im.alpha_composite(sp, (int(round(it["left"] * K)), int(round(it["top"] * K))))
    for (px, py) in it.get("pupils", []):
        d.ellipse([(px - 3.5) * K, (py - 3.5) * K, (px + 3.5) * K, (py + 3.5) * K], fill=(11, 11, 13, 255))
mask = Image.new("L", im.size, 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=52 * K, fill=255)
bg = Image.new("RGBA", im.size, (0, 0, 0, 255)); bg.paste(im, (0, 0), mask)
bg.convert("RGB").crop((0, 380 * K, W, H)).save(OBJ + "mock-lower.png")
print("ok")
