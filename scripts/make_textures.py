import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

rng = np.random.default_rng(7)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "textures") + "/"
os.makedirs(OUT, exist_ok=True)


def fft_noise(h, w, power, seed):
    """Periodic (seamless) 1/f^power noise, normalised to mean 0, std 1."""
    r = np.random.default_rng(seed)
    white = r.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    spec = np.fft.fft2(white) / (f ** power)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    return (n - n.mean()) / n.std()


def fibers(h, w, count, seed, length=(6, 34), spread=26):
    """Short curved paper fibres, lighter and darker, as a signed offset layer."""
    r = np.random.default_rng(seed)
    layer = Image.new("L", (w, h), 128)
    d = ImageDraw.Draw(layer)
    for _ in range(count):
        x, y = r.uniform(0, w), r.uniform(0, h)
        ang = r.uniform(0, np.pi)
        ln = r.uniform(*length)
        bend = r.uniform(-0.6, 0.6)
        pts = []
        for t in np.linspace(0, 1, 6):
            a = ang + bend * t
            pts.append((x + np.cos(a) * ln * t, y + np.sin(a) * ln * t))
        tone = 128 + int(r.choice([-1, 1]) * r.uniform(8, spread))
        d.line(pts, fill=tone, width=1)
    layer = layer.filter(ImageFilter.GaussianBlur(0.6))
    return np.asarray(layer, dtype=np.float32) - 128.0


# 1. paper grain for soft-light over any paper colour (mean ~128)
H = W = 1024
paper = 128.0
paper += fft_noise(H, W, 1.25, 1) * 16.0          # mottling
paper += fft_noise(H, W, 0.35, 2) * 9.0          # tooth
paper += fibers(H, W, 6500, 3, spread=46) * 2.0             # fibres
paper += rng.normal(0, 7.0, (H, W))              # fine grain
Image.fromarray(np.clip(paper, 0, 255).astype(np.uint8), "L").save(OUT + "np-paper.png", optimize=True)

# 2. film grain for overlay on photos (mean 128)
G = 512
grain = rng.normal(0, 1, (G, G))
grain = np.asarray(Image.fromarray(((grain * 40) + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.55)), dtype=np.float32)
grain = (grain - grain.mean()) / grain.std() * 34 + 128
Image.fromarray(np.clip(grain, 0, 255).astype(np.uint8), "L").save(OUT + "np-grain.png", optimize=True)

# 3. dark wall tile (seamless) — painted, slightly mottled, dusty
T = 512
base = np.array([31, 28, 43], dtype=np.float32)
mott = fft_noise(T, T, 1.6, 11) * 5.0 + fft_noise(T, T, 0.6, 12) * 2.2
fine = rng.normal(0, 2.4, (T, T))
lum = mott + fine
wall = base[None, None, :] + lum[:, :, None] * np.array([1.0, 0.95, 1.1])[None, None, :]
# dust specks, kept away from the tile edges so the repeat stays seamless
wimg = Image.fromarray(np.clip(wall, 0, 255).astype(np.uint8), "RGB")
d = ImageDraw.Draw(wimg)
for _ in range(90):
    x, y = rng.uniform(6, T - 6), rng.uniform(6, T - 6)
    s = rng.uniform(0.4, 1.3)
    c = int(rng.uniform(52, 80))
    d.ellipse([x - s, y - s, x + s, y + s], fill=(c, c - 2, c + 6))
wimg.save(OUT + "np-wall.png", optimize=True)

# 4. masking tape strip with torn ends (RGBA)
TW, TH = 420, 120
tape = np.zeros((TH, TW, 4), dtype=np.float32)
col = np.array([232, 222, 196], dtype=np.float32)
tone = fft_noise(TH, TW, 1.1, 21) * 5 + rng.normal(0, 2.5, (TH, TW))
crinkle = np.zeros((TH, TW), dtype=np.float32)
for _ in range(10):
    x0 = rng.uniform(0, TW)
    slope = rng.uniform(-0.5, 0.5)
    xs = x0 + slope * np.arange(TH)
    for yy in range(TH):
        xi = int(xs[yy])
        if 0 <= xi < TW:
            crinkle[yy, max(0, xi - 1):xi + 1] += rng.uniform(-9, 7)
crinkle = np.asarray(Image.fromarray((crinkle + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32) - 128
shade = tone + crinkle
tape[:, :, :3] = col[None, None, :] + shade[:, :, None]
alpha = np.full((TH, TW), 0.80) + fft_noise(TH, TW, 1.4, 22) * 0.035
# slightly denser along the long edges
yy = np.arange(TH)[:, None]
alpha += 0.06 * (np.exp(-yy / 5.0) + np.exp(-(TH - 1 - yy) / 5.0))
# torn ends: jagged random-walk profile on both sides
for side in (0, 1):
    prof = np.cumsum(rng.normal(0, 1.6, TH))
    prof = (prof - prof.min())
    prof = np.convolve(prof, np.ones(3) / 3, mode='same')
    prof = prof / max(prof.max(), 1) * 12 + rng.uniform(0, 1.5, TH)
    for y in range(TH):
        cut = int(prof[y])
        if side == 0:
            alpha[y, :cut] = 0
            if cut < TW:
                alpha[y, cut:cut + 2] *= 0.55
        else:
            alpha[y, TW - cut:] = 0
            if cut > 0:
                alpha[y, TW - cut - 2:TW - cut] *= 0.55
tape[:, :, 3] = np.clip(alpha, 0, 1) * 255
Image.fromarray(np.clip(tape, 0, 255).astype(np.uint8), "RGBA").save(OUT + "np-tape.png", optimize=True)

# previews: paper over cream, tape over wall
cream = np.array([239, 233, 220], dtype=np.float32) / 255.0
p = np.asarray(Image.open(OUT + "np-paper.png"), dtype=np.float32)[:400, :300] / 255.0
def soft_light(b, s):
    return np.where(s <= 0.5, b - (1 - 2 * s) * b * (1 - b), b + (2 * s - 1) * (np.where(b <= 0.25, ((16 * b - 12) * b + 4) * b, np.sqrt(b)) - b))
prev = soft_light(cream[None, None, :], p[:, :, None])
Image.fromarray((prev * 255).clip(0, 255).astype(np.uint8)).save(OUT + "preview-paper.png")
wall_prev = Image.open(OUT + "np-wall.png").convert("RGBA").crop((0, 0, 512, 200))
wall_prev.alpha_composite(Image.open(OUT + "np-tape.png"), (40, 40))
wall_prev.save(OUT + "preview-tape.png")
print("ok")
