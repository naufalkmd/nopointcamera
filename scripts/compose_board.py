"""Procedural circuit board for the code-built console, with the rendered parts placed on it (no AI)."""
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OBJ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") + "/"
K = 2                      # board pixels per CSS px
B = 10                     # CSS px of bleed on every side, so the board can drift behind the shell
O = B * K
W, H = (390 + 2 * B) * K, (844 + 2 * B) * K
rng = np.random.default_rng(11)

# ---- base solder mask ----
def fft_noise(h, w, power, seed):
    r = np.random.default_rng(seed)
    f = np.fft.fft2(r.standard_normal((h, w)))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    ff = np.sqrt(fx * fx + fy * fy)
    ff[0, 0] = 1
    n = np.real(np.fft.ifft2(f / ff ** power))
    return (n - n.mean()) / n.std()

base = np.array([14, 74, 44], float)
mott = fft_noise(H, W, 1.5, 3)[..., None] * np.array([2.5, 5, 3.5])
board = np.clip(base + mott + rng.normal(0, 1.6, (H, W, 1)), 0, 255).astype(np.uint8)
img = Image.fromarray(board, "RGB").convert("RGBA")
d = ImageDraw.Draw(img)

# ---- copper traces under the mask ----
TR = (30, 118, 70, 255)
TR_HI = (48, 140, 88, 255)

def route(x, y, steps):
    pts = [(x, y)]
    for _ in range(steps):
        dirn = rng.choice(["h", "v", "d"], p=[0.45, 0.45, 0.1])
        ln = rng.uniform(20, 120) * K / 2
        if dirn == "h":
            x += ln * rng.choice([-1, 1])
        elif dirn == "v":
            y += ln * rng.choice([-1, 1])
        else:
            s = rng.choice([-1, 1]); t = rng.choice([-1, 1])
            x += ln * 0.6 * s; y += ln * 0.6 * t
        x = float(np.clip(x, 0, W)); y = float(np.clip(y, 0, H))
        pts.append((x, y))
    return pts

for _ in range(70):
    pts = route(rng.uniform(0, W), rng.uniform(0, H), int(rng.integers(3, 7)))
    wdt = int(rng.choice([3, 4, 6]))
    d.line(pts, fill=TR, width=wdt, joint="curve")
    d.line(pts, fill=TR_HI, width=1)
    for (px, py) in (pts[0], pts[-1]):
        r = wdt + 3
        d.ellipse([px - r, py - r, px + r, py + r], fill=(201, 162, 74, 255))
        d.ellipse([px - r / 2.4, py - r / 2.4, px + r / 2.4, py + r / 2.4], fill=(20, 40, 28, 255))
# parallel bus lines
for bx, by, horiz, n, ln in [(40, 1330, True, 7, 300), (560, 1000, False, 6, 260), (40, 180, True, 5, 220), (620, 300, False, 6, 360)]:
    for i in range(n):
        if horiz:
            d.line([(O + bx, O + by + i * 9), (O + bx + ln, O + by + i * 9)], fill=TR, width=4)
        else:
            d.line([(O + bx + i * 9, O + by), (O + bx + i * 9, O + by + ln)], fill=TR, width=4)
# vias
for _ in range(160):
    x, y = rng.uniform(0, W), rng.uniform(0, H)
    d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(201, 162, 74, 255))
    d.ellipse([x - 1.6, y - 1.6, x + 1.6, y + 1.6], fill=(12, 28, 20, 255))
# mounting holes
for x, y in [(O + 48, O + 48), (O + 732, O + 48), (O + 60, O + 1634), (O + 720, O + 1634)]:
    d.ellipse([x - 18, y - 18, x + 18, y + 18], fill=(214, 176, 86, 255))
    d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(6, 10, 8, 255))
# silkscreen outlines + labels
font = ImageFont.load_default()
SILK = (226, 236, 228, 190)
for (x, y, w, h, lab) in [(150, 1470, 120, 90, "U1"), (560, 1120, 90, 70, "Q3"), (60, 880, 70, 46, "R12"), (640, 470, 60, 40, "C7"),
                          (300, 1580, 150, 60, "BT1"), (420, 960, 80, 60, "L2"), (80, 1230, 90, 70, "D4"), (560, 1560, 110, 60, "NPC-01")]:
    x, y = x + O, y + O
    d.rectangle([x, y, x + w, y + h], outline=SILK, width=2)
    d.text((x + 4, y - 14), lab, fill=SILK, font=font)
for _ in range(40):
    x, y = rng.uniform(0, W), rng.uniform(0, H)
    d.rectangle([x, y, x + 10, y + 6], fill=(201, 162, 74, 255))
    d.rectangle([x + 16, y, x + 26, y + 6], fill=(201, 162, 74, 255))

# ---- rainbow ribbon cable (CSS x 150-178, y 555-655) ----
cols = [(255, 59, 48), (255, 138, 30), (255, 210, 30), (60, 200, 90), (47, 140, 255), (142, 92, 255), (240, 240, 240), (40, 40, 44)]
rx0, ry0, ry1 = O + 150 * K, O + 552 * K, O + 656 * K
sw = 7
for i, c in enumerate(cols):
    x = rx0 + i * sw
    d.rectangle([x, ry0, x + sw - 1, ry1], fill=c + (255,))
    d.line([(x, ry0), (x, ry1)], fill=tuple(int(v * 0.7) for v in c) + (255,), width=1)
    d.line([(x + 2, ry0), (x + 2, ry1)], fill=tuple(min(255, int(v * 1.25) + 20) for v in c) + (255,), width=1)
for yy in (ry0 - 10, ry1 - 4):
    d.rounded_rectangle([rx0 - 6, yy, rx0 + sw * 8 + 6, yy + 16], radius=3, fill=(26, 26, 30, 255))
    d.line([(rx0 - 4, yy + 3), (rx0 + sw * 8 + 4, yy + 3)], fill=(70, 72, 80, 255), width=2)

# ---- LED strips with glow ----
glow = Image.new("RGB", (W, H), (0, 0, 0))
gd = ImageDraw.Draw(glow)
def led_strip(x0, x1, y, colors, n):
    x0, x1, y = x0 + O, x1 + O, y + O
    d.rounded_rectangle([x0 - 10, y - 13, x1 + 10, y + 13], radius=6, fill=(236, 236, 232, 255))
    d.line([(x0 - 8, y + 9), (x1 + 8, y + 9)], fill=(196, 170, 90, 255), width=2)
    step = (x1 - x0) / (n - 1)
    for i in range(n):
        x = x0 + i * step
        c = colors[int(i * len(colors) / n)]
        d.rectangle([x - 8, y - 8, x + 8, y + 8], fill=(250, 250, 250, 255))
        d.rectangle([x - 5, y - 5, x + 5, y + 5], fill=tuple(min(255, v + 90) for v in c) + (255,))
        gd.ellipse([x - 13, y - 13, x + 13, y + 13], fill=tuple(int(v * 0.75) for v in c))
PINK, CYAN, ORANGE = (255, 60, 200), (40, 230, 255), (255, 150, 30)
led_strip(64 * K, 326 * K, 438 * K, [PINK, CYAN, ORANGE], 15)
glow = glow.filter(ImageFilter.GaussianBlur(8))

# ---- rendered parts (render2 / parts2): contact shadows are baked into each sprite ----
import json
MAN = json.load(open(OBJ + "parts/manifest.json"))
for it in MAN:
    if it.get("overlay"):
        continue
    sp = Image.open(OBJ + "parts/" + it["key"] + ".png").convert("RGBA")
    img.alpha_composite(sp, (int(round(O + it["left"] * K)), int(round(O + it["top"] * K))))

rgb = ImageChops.screen(img.convert("RGB"), glow)
rgb.save(OBJ + "np-board.png", optimize=True)
rgb.save(OBJ + "np-board.webp", "WEBP", quality=90, method=6)
rgb.resize((W // 2, H // 2)).save(OBJ + "preview-board.jpg", quality=85)

print("done", rgb.size)
