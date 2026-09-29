"""Board parts v2: remodelled, textured and lit with render2 (no AI).

python3 parts2.py sheet [names...]   render test sprites and a contact sheet
python3 parts2.py layout             render every placement and write out/parts/manifest.json for compose
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import render2 as r2
from render2 import fbm, cell_rand, srgb2lin, tex_sample, vnoise
from render_objects import U, Z, capsule, ellipsoid, extrude, len2, poly2d, rbox, rcyl, rot, smin, sphere, star2d, torus, tri2d

os.makedirs(r2.OUT, exist_ok=True)
FONTS = "/System/Library/Fonts/Supplemental/"


def font(name, size):
    return ImageFont.truetype(FONTS + name, size)


def mix(a, b, t):
    t = np.asarray(t, float)
    if t.ndim == 1:
        t = t[:, None]
    return a * (1 - t) + b * t


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def text_tex(w, h, draw, bg=0):
    im = Image.new("L", (w, h), bg)
    draw(ImageDraw.Draw(im), im)
    return (np.asarray(im, float) / 255.0)[..., None]


# ------------------------------------------------------------------ chip (QFP)

CHIP_TEX = text_tex(512, 512, lambda d, im: (
    d.text((256, 190), "NPC-01", font=font("DIN Alternate Bold.ttf", 92), fill=255, anchor="mm"),
    d.text((256, 285), "NOPOINT", font=font("DIN Condensed Bold.ttf", 62), fill=235, anchor="mm"),
    d.text((256, 350), "2626  A7K", font=font("DIN Condensed Bold.ttf", 46), fill=210, anchor="mm")))


def chip(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    body = rbox(p - [0, 0.14, 0], [0.62, 0.1, 0.62], 0.04)
    d, m = body, Z(p)
    pins = 1e3
    for a, b in ((x, z), (z, x)):
        k = np.clip(np.round(a / 0.155), -3, 3)
        qa = a - k * 0.155
        ob = np.abs(b)
        foot = rbox(np.stack([qa, y - 0.018, ob - 0.75], 1), [0.032, 0.018, 0.07], 0.008)
        leg = rbox(np.stack([qa, y - 0.085, ob - 0.66], 1), [0.032, 0.07, 0.03], 0.01)
        pins = np.minimum(pins, np.minimum(foot, leg))
    d, m = U(d, m, pins, 1)
    dimple = sphere(p, [-0.4, 0.3, -0.4], 0.075)
    d = np.maximum(d, -dimple)
    m = np.where((np.abs(dimple) < 0.01) & (m == 0), 2, m)
    return d, m


def chip_albedo(q, n, alb):
    top = smooth(0.2, 0.235, q[:, 1])
    t = tex_sample(CHIP_TEX, (q[:, 0] + 0.62) / 1.24, (q[:, 2] + 0.62) / 1.24)[:, 0] * top
    return mix(alb, srgb2lin("#8C8F99")[None, :], t * 0.8)


def chip_rough(q, n, r):
    t = tex_sample(CHIP_TEX, (q[:, 0] + 0.62) / 1.24, (q[:, 2] + 0.62) / 1.24)[:, 0] * (q[:, 1] > 0.2)
    return r + 0.35 * t


CHIP = [dict(c="#17181D", rough=0.5, noise=0.04, rnoise=0.06, nfreq=60, albedo_fn=chip_albedo, rough_fn=chip_rough, coat=0.15),
        dict(c="#D7DBE2", rough=0.22, metal=1, noise=0.04),
        dict(c="#2A2C33", rough=0.7)]


# ------------------------------------------------------------------ electrolytic capacitor

def ecap(p):
    body = rcyl(p - [0, 0.55, 0], 0.42, 0.55, 0.09)
    d = np.maximum(body, -rcyl(p - [0, 1.12, 0], 0.33, 0.06, 0.01))
    alu = rcyl(p - [0, 1.05, 0], 0.335, 0.012, 0.004)
    groove = np.minimum(rbox(p - [0, 1.07, 0], [0.26, 0.02, 0.018], 0.01), rbox(p - [0, 1.07, 0], [0.018, 0.02, 0.26], 0.01))
    alu = np.maximum(alu, -groove)
    m = Z(p)
    d, m = U(d, m, alu, 1)
    return d, m


def ecap_albedo(q, n, alb):
    th = np.arctan2(q[:, 2], q[:, 0])
    da = np.abs((th - 1.05 + np.pi) % (2 * np.pi) - np.pi)
    stripe = smooth(0.5, 0.44, da) * smooth(1.06, 1.0, q[:, 1]) * smooth(0.04, 0.1, q[:, 1])
    out = mix(alb, srgb2lin("#C9D6F2")[None, :], stripe)
    fr = (q[:, 1] / 0.17) % 1
    dash = (da < 0.13) & (fr > 0.42) & (fr < 0.58) & (q[:, 1] > 0.12) & (q[:, 1] < 0.98)
    return mix(out, srgb2lin("#1B2A55")[None, :], dash * 0.9)


ECAP = [dict(c="#2349C8", rough=0.3, coat=0.5, albedo_fn=ecap_albedo, noise=0.04),
        dict(c="#D9DDE4", rough=0.26, metal=1, noise=0.02, rnoise=0.05)]


# ------------------------------------------------------------------ resistor (legs bent into the board)

def resistor(p):
    y0 = 0.2
    body = smin(capsule(p, [-0.3, y0, 0], [0.3, y0, 0], 0.14),
                np.minimum(sphere(p, [-0.34, y0, 0], 0.18), sphere(p, [0.34, y0, 0], 0.18)), 0.1)
    d, m = body, Z(p)
    x = p[:, 0]
    for cx, mi in ((-0.3, 2), (-0.14, 3), (0.0, 4), (0.3, 5)):
        m = np.where((np.abs(x - cx) < 0.045) & (m == 0), mi, m)
    leads = np.minimum.reduce([capsule(p, [-0.5, y0, 0], [-0.64, y0, 0], 0.03), capsule(p, [-0.64, y0, 0], [-0.68, 0.0, 0], 0.03),
                               capsule(p, [0.5, y0, 0], [0.64, y0, 0], 0.03), capsule(p, [0.64, y0, 0], [0.68, 0.0, 0], 0.03)])
    d, m = U(d, m, leads, 1)
    solder = np.minimum(ellipsoid(p, [-0.68, 0.0, 0], [0.11, 0.06, 0.11]), ellipsoid(p, [0.68, 0.0, 0], [0.11, 0.06, 0.11]))
    d, m = U(d, m, solder, 6)
    return d, m


RESISTOR = [dict(c="#E2CFA0", rough=0.4, coat=0.4, noise=0.08), dict(c="#D7DBE2", rough=0.2, metal=1),
            dict(c="#7A3E12", rough=0.35, coat=0.4), dict(c="#161616", rough=0.35, coat=0.4),
            dict(c="#E0231F", rough=0.35, coat=0.4), dict(c="#D9A62B", rough=0.25, metal=1),
            dict(c="#BFC3CA", rough=0.35, metal=1, noise=0.1, nfreq=30)]


# ------------------------------------------------------------------ AA battery

def _bat_tex(d, im):
    # u runs along the battery, v around it; 1024 x 1036 keeps letters square on a 1.68 x 1.70 unit wrap
    W, H = im.size
    y = int(H * 0.33)
    d.text((int(W * 0.63), y), "NOPO", font=font("Arial Black.ttf", 150), fill=255, anchor="mm")
    d.text((int(W * 0.17), y), "1.5V AA", font=font("DIN Condensed Bold.ttf", 120), fill=255, anchor="mm")
    d.text((int(W * 0.935), y), "+", font=font("Arial Black.ttf", 130), fill=255, anchor="mm")


BAT_TEX = text_tex(1024, 1036, _bat_tex)
BR = 0.27


def battery(p):
    qq = np.stack([p[:, 1] - BR, p[:, 0], p[:, 2]], 1)
    d = rcyl(qq, BR, 0.84, 0.045)
    nub = rcyl(qq - [0, 0.87, 0], 0.1, 0.05, 0.02)
    d = np.minimum(d, nub)
    m = np.where((np.abs(p[:, 0]) > 0.8) | (nub < 0.004), 1, 0)
    return d, m


def battery_albedo(q, n, alb):
    th = np.arctan2(q[:, 1] - BR, q[:, 2])
    u = (q[:, 0] + 0.84) / 1.68
    v = 1 - (th + np.pi) / (2 * np.pi)
    t = tex_sample(BAT_TEX, u, v)[:, 0]
    lime = srgb2lin("#B8F23A")[None, :]
    black = srgb2lin("#141418")[None, :]
    white = srgb2lin("#F2F2F2")[None, :]
    left = smooth(0.338, 0.342, u)[:, None]
    base = mix(black, lime, left)
    ink = mix(white, black, left)
    return mix(base, ink, smooth(0.3, 0.7, t))


BATTERY = [dict(c="#FFFFFF", rough=0.28, coat=0.7, albedo_fn=battery_albedo, noise=0.02),
           dict(c="#D7DBE2", rough=0.18, metal=1, noise=0.05, nfreq=40)]


# ------------------------------------------------------------------ cassette

def _cas_tex(d, im):
    W, H = im.size
    d.rectangle([0, 0, W, H], fill=255)
    for i, y in enumerate(range(118, 200, 26)):
        d.line([(70, y), (W - 60, y)], fill=205, width=2)
    d.text((80, 58), "no point mix", font=font("Chalkboard.ttc", 70), fill=30, anchor="lm")
    d.text((W - 70, 70), "vol. 3", font=font("Chalkboard.ttc", 44), fill=60, anchor="rm")
    d.rectangle([22, 24, 72, 88], outline=40, width=5)
    d.text((47, 57), "A", font=font("Arial Black.ttf", 42), fill=40, anchor="mm")
    d.text((W - 40, H - 36), "C-60", font=font("DIN Condensed Bold.ttf", 40), fill=40, anchor="rm")


CAS_TEX = text_tex(1024, 460, _cas_tex)
CX, CZ0, CZ1 = 0.8, -0.5, 0.22        # label rectangle on top
HUBS = ((-0.38, -0.05), (0.38, -0.05))
TRAP = [(-0.56, 0.3), (0.56, 0.3), (0.46, 0.58), (-0.46, 0.58)]


def cassette(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    body = rbox(p - [0, 0.1, 0], [0.92, 0.1, 0.58], 0.045)
    d = body
    for hx, hz in HUBS:
        d = np.maximum(d, -rcyl(p - [hx, 0.21, hz], 0.12, 0.03, 0.006))
    win = rbox(p - [0, 0.21, -0.05], [0.2, 0.02, 0.075], 0.02)
    d = np.maximum(d, -win)
    trap = extrude(poly2d(x, z, TRAP), y - 0.2, 0.018, 0.012)
    d = smin(d, trap, 0.01)
    m = Z(p)
    top = y > 0.185
    lab = top & (np.abs(x) < CX) & (z > CZ0) & (z < CZ1)
    m = np.where(lab, 1, m)
    hub_r = np.minimum(len2(x - HUBS[0][0], z - HUBS[0][1]), len2(x - HUBS[1][0], z - HUBS[1][1]))
    m = np.where((hub_r < 0.125) & (y < 0.2), 3, m)
    m = np.where((np.abs(x) < 0.215) & (np.abs(z + 0.05) < 0.09) & (y < 0.2), 2, m)
    screws = np.minimum.reduce([rcyl(p - [sx, 0.2, sz], 0.035, 0.012, 0.008) for sx, sz in ((-0.83, -0.49), (0.83, -0.49), (-0.83, 0.49), (0.83, 0.49), (0, 0.47))])
    d, m = U(d, m, screws, 4)
    return d, m


def cas_label(q, n, alb):
    u = (q[:, 0] + CX) / (2 * CX)
    v = (q[:, 2] - CZ0) / (CZ1 - CZ0)
    t = tex_sample(CAS_TEX, u, v)[:, 0]
    paper = srgb2lin("#F0E9DA")[None, :] * (1 + 0.06 * (fbm(q * 60, 3, 3) - 0.5))[:, None]
    ink = srgb2lin("#1C2F7A")[None, :]
    out = mix(ink, paper, t)
    # two printed stripes under the writing
    zz = q[:, 2]
    out = np.where(((zz > -0.24) & (zz < -0.2))[:, None], srgb2lin("#FF6A2B")[None, :], out)
    out = np.where(((zz > -0.2) & (zz < -0.16))[:, None], srgb2lin("#FF3D9A")[None, :], out)
    return out


def cas_window(q, n, alb):
    # brown tape wound on the two reels, seen through the smoked window
    r = np.minimum(len2(q[:, 0] - HUBS[0][0], q[:, 2] - HUBS[0][1]), len2(q[:, 0] - HUBS[1][0], q[:, 2] - HUBS[1][1]))
    tape = smooth(0.3, 0.26, r)
    return mix(srgb2lin("#07080A")[None, :], srgb2lin("#3A1F12")[None, :], tape * 0.9)


def cas_hub(q, n, alb):
    hx = np.where(q[:, 0] < 0, HUBS[0][0], HUBS[1][0])
    a = np.arctan2(q[:, 2] - HUBS[0][1], q[:, 0] - hx)
    r = len2(q[:, 0] - hx, q[:, 2] - HUBS[0][1])
    teeth = (np.cos(a * 6) > 0.3) & (r < 0.07) & (r > 0.04)
    ring = (r > 0.07) & (r < 0.1)
    out = np.tile(srgb2lin("#0A0B0D"), (len(q), 1))
    out = np.where((teeth | ring)[:, None], srgb2lin("#F2EFE8")[None, :], out)
    return out


CASSETTE = [dict(c="#1A1B21", rough=0.28, coat=0.35, noise=0.1, nfreq=24),
            dict(c="#F0E9DA", rough=0.75, albedo_fn=cas_label, noise=0, rnoise=0.05),
            dict(c="#0A0B0D", rough=0.06, coat=0.8, albedo_fn=cas_window, noise=0, rnoise=0.02),
            dict(c="#0A0B0D", rough=0.5, albedo_fn=cas_hub, noise=0),
            dict(c="#C9CED6", rough=0.25, metal=1)]


# ------------------------------------------------------------------ googly eyes

def googly(p):
    d = 1e3
    for cx in (-0.34, 0.34):
        base = rcyl(p - [cx, 0.02, 0], 0.31, 0.02, 0.01)
        dome = ellipsoid(p, [cx, 0.03, 0], [0.3, 0.15, 0.3])
        dome = np.maximum(dome, -(p[:, 1] - 0.03))
        d = np.minimum(d, np.minimum(base, dome))
    return d, Z(p)


GOOGLY = [dict(c="#F3F4F7", rough=0.55, coat=1.0, coat_rough=0.03, noise=0.02)]


# ------------------------------------------------------------------ jelly beans

BEANS = [((-0.4, 0.2), 0.4, 0), ((0.28, 0.28), -0.7, 1), ((0.02, -0.24), 1.2, 2), ((-0.5, -0.34), 2.0, 3), ((0.58, -0.16), 0.2, 4),
         ((-0.1, 0.52), 2.6, 1)]


def beans(p):
    d, m = np.full(len(p), 1e3), Z(p)
    for (cx, cz), a, mi in BEANS:
        q = rot(p - np.array([cx, 0.13, cz]), "y", a)
        b = smin(ellipsoid(q, [-0.1, 0, 0.025], [0.18, 0.13, 0.135]), ellipsoid(q, [0.1, 0, -0.025], [0.18, 0.13, 0.135]), 0.08)
        d, m = U(d, m, b, mi)
    return d, m


def speckle(q, n, alb):
    s = vnoise(q * 38, 5) > 0.74
    return mix(alb, alb * 0.35, s * 0.8)


BEANSM = [dict(c=c, rough=0.24, coat=0.9, wrap=0.6, noise=0.05, **({"albedo_fn": speckle} if i in (1, 3) else {}))
          for i, c in enumerate(["#FF2D55", "#FFD21E", "#3CE06B", "#8E5CFF", "#FF8A1E"])]


# ------------------------------------------------------------------ coin cell

CELL_TEX = text_tex(512, 512, lambda d, im: (
    d.text((256, 200), "CR2032", font=font("DIN Alternate Bold.ttf", 90), fill=255, anchor="mm"),
    d.text((256, 300), "3V", font=font("DIN Alternate Bold.ttf", 70), fill=255, anchor="mm"),
    d.text((256, 405), "+", font=font("Arial Black.ttf", 80), fill=255, anchor="mm")))


def coincell(p):
    d = rcyl(p - [0, 0.075, 0], 0.62, 0.075, 0.03)
    d = np.minimum(d, rcyl(p - [0, 0.15, 0], 0.52, 0.018, 0.01))
    return d, Z(p)


def cell_bump(q):
    t = tex_sample(CELL_TEX, (q[:, 0] + 0.52) / 1.04, (q[:, 2] + 0.52) / 1.04)[:, 0] * (q[:, 1] > 0.15)
    a = np.arctan2(q[:, 2], q[:, 0])
    r = len2(q[:, 0], q[:, 2])
    brushed = vnoise(np.stack([r * 160, a * 3, q[:, 1] * 2], 1), 9)
    return t * 0.005 + brushed * 0.0008


def cell_rough(q, n, r):
    a = np.arctan2(q[:, 2], q[:, 0])
    rr = len2(q[:, 0], q[:, 2])
    return r + 0.12 * (vnoise(np.stack([rr * 90, a * 2, q[:, 1]], 1), 4) - 0.5)


COINCELL = [dict(c="#D6DAE1", rough=0.2, metal=1, bump_fn=cell_bump, bump=1.0, rough_fn=cell_rough, noise=0.03)]


# ------------------------------------------------------------------ gumballs

SQ = 0.88   # vertical squash that keeps balls round in the oblique view


def gumball(p):
    return ellipsoid(p, [0, 0.6 * SQ, 0], [0.6, 0.6 * SQ, 0.6]), Z(p)


def gum(c):
    return [dict(c=c, rough=0.3, coat=1.0, coat_rough=0.05, wrap=0.45, noise=0.06, nfreq=20)]


# ------------------------------------------------------------------ disco ball

DR, DROWS, DCOLS = 0.6, 14, 28


def disco(p):
    return ellipsoid(p, [0, DR * SQ + 0.01, 0], [DR, DR * SQ, DR]), Z(p)


def _tile(q):
    c = (q - np.array([0, DR * SQ + 0.01, 0])) * np.array([1, 1 / SQ, 1])
    r = np.maximum(np.linalg.norm(c, axis=1), 1e-6)
    th = np.arctan2(c[:, 2], c[:, 0])
    ph = np.arccos(np.clip(c[:, 1] / r, -1, 1))
    fr = ph / math.pi * DROWS
    row = np.floor(fr)
    ncol = np.maximum(np.round(DCOLS * np.sin((row + 0.5) / DROWS * math.pi)), 4)
    fc = (th + math.pi) / (2 * math.pi) * ncol
    col = np.floor(fc)
    return row, col, ncol, fr - row, fc - col


def disco_normals(q, n):
    row, col, ncol, _, _ = _tile(q)
    ph2 = (row + 0.5) / DROWS * math.pi
    th2 = (col + 0.5) / ncol * 2 * math.pi - math.pi
    ids = np.stack([row, col], 1).astype(np.int64)
    jx = (cell_rand(ids, 1) - 0.5) * 0.34
    jz = (cell_rand(ids, 2) - 0.5) * 0.34
    nn = np.stack([np.sin(ph2) * np.cos(th2) + jx, np.cos(ph2), np.sin(ph2) * np.sin(th2) + jz], 1)
    return nn / np.linalg.norm(nn, axis=1, keepdims=True)


def disco_albedo(q, n, alb):
    row, col, _, fr, fc = _tile(q)
    ids = np.stack([row, col], 1).astype(np.int64)
    tint = 0.82 + 0.3 * cell_rand(ids, 3)
    grout = (np.minimum(fr, 1 - fr) < 0.05) | (np.minimum(fc, 1 - fc) < 0.05)
    out = alb * tint[:, None]
    return np.where(grout[:, None], srgb2lin("#15161A")[None, :], out)


def disco_rough(q, n, r):
    row, col, _, fr, fc = _tile(q)
    grout = (np.minimum(fr, 1 - fr) < 0.05) | (np.minimum(fc, 1 - fc) < 0.05)
    ids = np.stack([row, col], 1).astype(np.int64)
    return np.where(grout, 0.9, 0.04 + 0.08 * cell_rand(ids, 4))


SPARK = np.array([srgb2lin(h) for h in ("#FF4FD8", "#3CF2FF", "#C6FF3A", "#FFFFFF", "#FFB21E")])


def disco_spark(q, n, alb):
    # a few tiles catching the console's neon, like a real mirror ball under party lights
    row, col, _, fr, fc = _tile(q)
    ids = np.stack([row, col], 1).astype(np.int64)
    on = (cell_rand(ids, 11) > 0.9) & (np.minimum(fr, 1 - fr) > 0.05) & (np.minimum(fc, 1 - fc) > 0.05)
    pick = (cell_rand(ids, 12) * len(SPARK)).astype(int) % len(SPARK)
    return SPARK[pick] * (on * (0.5 + 0.8 * cell_rand(ids, 13)))[:, None]


DISCO = [dict(c="#E9ECF2", metal=1, rough=0.05, normal_fn=disco_normals, albedo_fn=disco_albedo, rough_fn=disco_rough, emit_fn=disco_spark, noise=0, rnoise=0)]


# ------------------------------------------------------------------ rubber duck

def duck(p):
    q = p - [0, 0.58, 0]
    body = ellipsoid(q, [0, -0.2, 0], [0.62, 0.38, 0.47])
    tail = ellipsoid(rot(q - [-0.52, 0.0, 0], "z", -0.6), [0, 0, 0], [0.22, 0.1, 0.16])
    b = smin(body, tail, 0.12)
    b = smin(b, sphere(q, [0.24, 0.3, 0], 0.3), 0.14)
    wing = np.minimum(ellipsoid(q, [-0.06, -0.1, 0.43], [0.3, 0.15, 0.08]), ellipsoid(q, [-0.06, -0.1, -0.43], [0.3, 0.15, 0.08]))
    b = smin(b, wing, 0.05)
    b = np.maximum(b, -(p[:, 1] - 0.0))
    d, m = b, Z(p)
    d, m = U(d, m, ellipsoid(q, [0.56, 0.24, 0], [0.2, 0.07, 0.15]), 1)
    eyes = np.minimum(sphere(q, [0.45, 0.4, 0.16], 0.05), sphere(q, [0.45, 0.4, -0.16], 0.05))
    d, m = U(d, m, eyes, 2)
    return d, m


DUCK = [dict(c="#FFD21E", rough=0.34, coat=0.35, wrap=0.35, noise=0.05), dict(c="#FF7A1A", rough=0.3, coat=0.3, wrap=0.3),
        dict(c="#0E0E12", rough=0.08, coat=1.0)]


# ------------------------------------------------------------------ dice

PIPS = []
_a = 0.25
_pat = {1: [(0, 0)], 2: [(-_a, -_a), (_a, _a)], 3: [(-_a, -_a), (0, 0), (_a, _a)],
        4: [(-_a, -_a), (-_a, _a), (_a, -_a), (_a, _a)], 5: [(-_a, -_a), (-_a, _a), (_a, -_a), (_a, _a), (0, 0)],
        6: [(-_a, -_a), (-_a, 0), (-_a, _a), (_a, -_a), (_a, 0), (_a, _a)]}
for _axis, _sign, _n in [(1, 1, 5), (1, -1, 2), (2, 1, 3), (2, -1, 4), (0, 1, 6), (0, -1, 1)]:
    for _u, _v in _pat[_n]:
        _c = [0.0, 0.5, 0.0]
        _c[_axis] += 0.56 * _sign
        _o = [i for i in range(3) if i != _axis]
        _c[_o[0]] += _u
        _c[_o[1]] += _v
        PIPS.append(_c)


def dice(p):
    box = rbox(p - [0, 0.5, 0], [0.5, 0.5, 0.5], 0.12)
    dp = np.min(np.stack([sphere(p, c, 0.095) for c in PIPS], 1), 1)
    d = np.maximum(box, -dp)
    m = np.where(np.abs(dp) < 0.012, 1, 0)
    return d, m


DICE = [dict(c="#E8202A", rough=0.12, coat=0.7, wrap=0.55, noise=0.03), dict(c="#FAFAFA", rough=0.5)]


# ------------------------------------------------------------------ coin

def coin(p):
    q = p - [0, 0.075, 0]
    ang = np.arctan2(q[:, 2], q[:, 0])
    rr = len2(q[:, 0], q[:, 2]) - (0.62 + 0.006 * np.sign(np.sin(ang * 80)))
    dy = np.abs(q[:, 1]) - 0.05
    body = np.minimum(np.maximum(rr, dy), 0) + len2(np.maximum(rr, 0), np.maximum(dy, 0)) - 0.025
    d = np.minimum(body, torus(q - [0, 0.065, 0], 0.54, 0.028))
    st = extrude(star2d(q[:, 0], -q[:, 2], 0.3, 0.45), q[:, 1] - 0.06, 0.018, 0.012)
    d = np.minimum(d, st)
    return d * 0.9, Z(p)


def coin_bump(q):
    return vnoise(q * np.array([220, 5, 30]), 2) * 0.0005 + fbm(q * 20, 2, 3) * 0.0008


COIN = [dict(c="#F0BE3E", rough=0.26, metal=1, rnoise=0.1, nfreq=8, noise=0.05, bump_fn=coin_bump)]


# ------------------------------------------------------------------ donut

SPR = []
_rng = np.random.default_rng(5)
for _i in range(40):
    a = _rng.uniform(0, 2 * np.pi)
    ph = _rng.uniform(0.35, 1.35)
    c = np.array([(0.55 + 0.33 * np.cos(ph)) * np.cos(a), 0.3 + 0.33 * np.sin(ph), (0.55 + 0.33 * np.cos(ph)) * np.sin(a)])
    nrm = np.array([np.cos(ph) * np.cos(a), np.sin(ph), np.cos(ph) * np.sin(a)])
    rv = _rng.normal(size=3)
    td = rv - nrm * (rv @ nrm)
    td /= np.linalg.norm(td)
    SPR.append((c - td * 0.055, c + td * 0.055, _i % 4))


def donut(p):
    q = p - [0, 0.3, 0]
    d = torus(q, 0.55, 0.3)
    m = Z(p)
    ang = np.arctan2(q[:, 2], q[:, 0])
    ic = np.maximum(torus(q, 0.55, 0.322), -(q[:, 1] - 0.02 + 0.07 * np.sin(ang * 7) + 0.03 * np.sin(ang * 13 + 1)))
    d, m = U(d, m, ic, 1)
    near = ic < 0.12
    if near.any():
        pn = p[near]
        ds = np.full(len(pn), 1e3)
        ms = np.full(len(pn), 2)
        for a_, b_, ci in SPR:
            dc = capsule(pn, a_, b_, 0.024)
            s = dc < ds
            ds = np.where(s, dc, ds)
            ms = np.where(s, 2 + ci, ms)
        dd = d[near]
        mm = m[near]
        s = ds < dd
        d[near] = np.where(s, ds, dd)
        m[near] = np.where(s, ms, mm)
    return d, m


def dough_albedo(q, n, alb):
    r = len2(q[:, 0], q[:, 2])
    band = smooth(0.09, 0.02, np.abs(q[:, 1] - 0.3)) * smooth(0.7, 0.8, r)
    return mix(alb * (0.85 + 0.3 * fbm(q * 8, 3, 1))[:, None], srgb2lin("#F4D9A6")[None, :], band * 0.8)


DONUT = [dict(c="#C98542", rough=0.75, albedo_fn=dough_albedo, bump_fn=lambda q: fbm(q * 18, 3, 2) * 0.012, noise=0),
         dict(c="#FF5FA8", rough=0.16, coat=0.8, wrap=0.3, bump_fn=lambda q: fbm(q * 10, 2, 4) * 0.004, noise=0.04),
         dict(c="#FFD21E", rough=0.3, coat=0.6), dict(c="#FFFFFF", rough=0.3, coat=0.6),
         dict(c="#3D7BFF", rough=0.3, coat=0.6), dict(c="#3CE0B0", rough=0.3, coat=0.6)]


# ------------------------------------------------------------------ tin robot

def robot(p):
    body = rbox(p - [0, 0.5, 0], [0.34, 0.3, 0.26], 0.07)
    head = rbox(p - [0, 1.03, 0], [0.3, 0.2, 0.24], 0.07)
    neck = rcyl(p - [0, 0.83, 0], 0.1, 0.05, 0.02)
    d = np.minimum(np.minimum(body, head), neck)
    m = Z(p)
    feet = np.minimum(rbox(p - [-0.17, 0.08, 0.03], [0.13, 0.08, 0.2], 0.04), rbox(p - [0.17, 0.08, 0.03], [0.13, 0.08, 0.2], 0.04))
    d, m = U(d, m, feet, 5)
    arms = np.minimum(capsule(p, [-0.4, 0.68, 0], [-0.5, 0.36, 0.08], 0.075), capsule(p, [0.4, 0.68, 0], [0.5, 0.36, 0.08], 0.075))
    d, m = U(d, m, arms, 0)
    d, m = U(d, m, capsule(p, [0, 1.22, 0], [0, 1.42, 0], 0.022), 1)
    d, m = U(d, m, sphere(p, [0, 1.46, 0], 0.065), 2)
    eyes = np.minimum(sphere(p, [-0.13, 1.07, 0.22], 0.07), sphere(p, [0.13, 1.07, 0.22], 0.07))
    d, m = U(d, m, eyes, 3)
    panel = rbox(p - [0, 0.52, 0.265], [0.2, 0.14, 0.02], 0.02)
    d, m = U(d, m, panel, 4)
    rivets = np.minimum.reduce([sphere(p, [sx, sy, 0.25], 0.022) for sx in (-0.26, 0.26) for sy in (0.28, 0.72)])
    d, m = U(d, m, rivets, 1)
    mouth = rbox(p - [0, 0.93, 0.24], [0.13, 0.025, 0.02], 0.01)
    d, m = U(d, m, mouth, 5)
    return d, m


def panel_albedo(q, n, alb):
    x, y = q[:, 0], q[:, 1]
    dial = (len2(x + 0.09, y - 0.55) < 0.055) | (len2(x - 0.09, y - 0.55) < 0.055)
    out = np.where(dial[:, None], srgb2lin("#1A1A1E")[None, :], alb)
    slot = (np.abs(y - 0.44) < 0.012) & (np.abs(x) < 0.15)
    return np.where(slot[:, None], srgb2lin("#1A1A1E")[None, :], out)


ROBOT = [dict(c="#8DB3DA", rough=0.3, coat=0.6, noise=0.07, nfreq=14), dict(c="#D8DCE3", rough=0.15, metal=1),
         dict(c="#FF3B2F", rough=0.15, coat=0.8, emit=0.5), dict(c="#3CF2FF", rough=0.1, coat=1.0, emit=1.6),
         dict(c="#FFB21E", rough=0.35, coat=0.5, albedo_fn=panel_albedo, emit_fn=lambda q, n, a: a * 0.15), dict(c="#2C2F38", rough=0.45)]


# ------------------------------------------------------------------ fan (housing is baked, blades spin in CSS)

FAN_G = 0.0


def fan_housing(p):
    frame = rbox(p - [0, 0.13, 0], [0.8, 0.13, 0.8], 0.07)
    hole = rcyl(p - [0, 0.2, 0], 0.7, 0.3, 0.02)
    d = np.maximum(frame, -hole)
    for x, z in ((0.62, 0.62), (-0.62, 0.62), (0.62, -0.62), (-0.62, -0.62)):
        d = np.maximum(d, -rcyl(p - [x, 0.2, z], 0.055, 0.3, 0.01))
    m = Z(p)
    floor = rcyl(p - [0, 0.02, 0], 0.72, 0.02, 0.01)
    struts = np.minimum(rbox(p - [0, 0.05, 0], [0.72, 0.02, 0.03], 0.01), rbox(p - [0, 0.05, 0], [0.03, 0.02, 0.72], 0.01))
    d, m = U(d, m, np.minimum(floor, struts), 1)
    return d, m


FANH = [dict(c="#1C1D22", rough=0.5, noise=0.1, nfreq=20), dict(c="#0B0C0F", rough=0.7)]


def fan_blades(p):
    q = p - [0, 0.14, 0]
    hub = rcyl(q, 0.2, 0.05, 0.035)
    d, m = hub, Z(p)
    th = np.arctan2(q[:, 2], q[:, 0])
    k = np.round(th / (2 * math.pi / 7))
    a = -k * (2 * math.pi / 7)
    c, s = np.cos(a), np.sin(a)
    x = c * q[:, 0] - s * q[:, 2]
    z = s * q[:, 0] + c * q[:, 2]
    bl = rbox(np.stack([x - 0.42, q[:, 1] + 0.01 + 0.06 * (z / 0.2), z], 1), [0.25, 0.012, 0.11], 0.01)
    d, m = U(d, m, bl * 0.8, 1)
    return d, m


FAN_TEX = text_tex(256, 256, lambda d, im: (d.ellipse([8, 8, 248, 248], fill=255), d.text((128, 128), "12V", font=font("DIN Alternate Bold.ttf", 70), fill=60, anchor="mm")))


def hub_albedo(q, n, alb):
    t = tex_sample(FAN_TEX, (q[:, 0] + 0.2) / 0.4, (q[:, 2] + 0.2) / 0.4)[:, 0] * (q[:, 1] > 0.18)
    lime = srgb2lin("#C6FF3A")[None, :]
    return np.where((t > 0.1)[:, None], mix(srgb2lin("#1A1A1E")[None, :], lime, smooth(0.2, 0.6, t)), alb)


FANB = [dict(c="#2A2C33", rough=0.4, coat=0.3, albedo_fn=hub_albedo, noise=0), dict(c="#33363F", rough=0.35, coat=0.3, noise=0.05)]


# ------------------------------------------------------------------ registry

OBJ = {
    "chip": (chip, CHIP), "ecap": (ecap, ECAP), "resistor": (resistor, RESISTOR), "battery": (battery, BATTERY),
    "cassette": (cassette, CASSETTE), "googly": (googly, GOOGLY), "beans": (beans, BEANSM), "coincell": (coincell, COINCELL),
    "gum-pink": (gumball, gum("#FF4FA3")), "gum-blue": (gumball, gum("#2FC8FF")), "gum-yellow": (gumball, gum("#FFD21E")),
    "disco": (disco, DISCO), "duck": (duck, DUCK), "dice": (dice, DICE), "coin": (coin, COIN), "donut": (donut, DONUT),
    "robot": (robot, ROBOT), "fanhousing": (fan_housing, FANH),
}

# CSS px on the 390x844 board: name, centre x, centre y (the footprint centre), px per unit, yaw in degrees
PLACES = [
    # left of the print slot, under the UFO sticker
    ("duck", 42, 474, 30, 25), ("dice", 92, 486, 22, -18),
    # right of the print slot
    ("donut", 356, 424, 22, 0), ("battery", 328, 474, 36, 6),
    # between the d-pad and the A/B pod
    ("chip", 196, 520, 25, 8), ("fanhousing", 190, 603, 30, 0),
    # the ledge below the d-pad
    ("coin", 100, 641, 19, 0),
    # above the speaker
    ("disco", 283, 652, 40, 0), ("robot", 354, 660, 34, -22),
    # right edge beside A
    ("resistor", 375, 548, 20, 90), ("ecap", 372, 600, 22, 0),
    # left edge beside the d-pad
    ("ecap", 17, 520, 20, 0), ("resistor", 15, 598, 20, 90),
    # bottom pocket
    ("cassette", 146, 774, 52, -5), ("beans", 230, 754, 34, 0), ("googly", 226, 817, 32, 0), ("coincell", 100, 826, 23, 0),
    # bottom-right corner
    ("gum-pink", 294, 826, 17, 0), ("gum-blue", 318, 818, 15, 0), ("gum-yellow", 340, 804, 13, 0),
    # peeking out beside the bezel
    ("resistor", 7, 160, 18, 90), ("ecap", 6, 300, 18, 0), ("resistor", 384, 226, 18, 90),
]


# ------------------------------------------------------------------ console controls (same studio as the parts)

LIME = dict(c="#B8F23A", rough=0.22, coat=0.6, wrap=0.4, emit=0.06, noise=0.03)


def dpad(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    ring = np.maximum(rcyl(p - [0, 0.1, 0], 1.0, 0.1, 0.05), -rcyl(p - [0, 0.1, 0], 0.8, 0.2, 0.02))
    d, m = ring, Z(p)
    cross = np.minimum(np.maximum(np.abs(x) - 0.64, np.abs(z) - 0.21), np.maximum(np.abs(x) - 0.21, np.abs(z) - 0.64))
    c3 = extrude(cross + 0.05, y - 0.3, 0.1, 0.05)
    c3 = np.maximum(c3, -sphere(p, [0, 0.72, 0], 0.36))
    c3 = np.minimum(c3, rcyl(p - [0, 0.1, 0], 0.25, 0.1, 0.02))
    d, m = U(d, m, c3, 1)
    return d, m


def dpad_bump(q):
    x, z = q[:, 0], q[:, 2]
    t = np.minimum.reduce([tri2d(x, -(z + 0.47), 0.075), tri2d(x, z - 0.47, 0.075), tri2d(z, x - 0.47, 0.075), tri2d(z, -(x + 0.47), 0.075)])
    return smooth(0.012, -0.012, t) * 0.008 * (q[:, 1] > 0.4)


DPAD = [LIME, dict(c="#16161A", rough=0.36, coat=0.35, noise=0.03, bump_fn=dpad_bump)]


def gb_button(p):
    d, m = rcyl(p - [0, 0.1, 0], 0.86, 0.1, 0.06), Z(p)
    cap = rcyl(p - [0, 0.32, 0], 0.64, 0.2, 0.17)
    cap = smin(cap, sphere(p, [0, -0.22, 0], 0.8), 0.05)
    cap = np.maximum(cap, -(p[:, 1] - 0.2))
    d, m = U(d, m, cap, 1)
    return d, m


GB_BUTTON = [LIME, dict(c="#141418", rough=0.14, coat=0.9, noise=0.02)]


def gb_pill(p):
    q = rot(p, "y", 0.42)
    sx = np.maximum(np.abs(q[:, 0]) - 0.62, 0)
    collar = extrude(len2(sx, q[:, 2]) - 0.3, q[:, 1] - 0.09, 0.07, 0.03)
    d, m = collar, Z(p)
    d, m = U(d, m, capsule(q, [-0.5, 0.2, 0], [0.5, 0.2, 0], 0.16), 1)
    return d, m


GB_PILL = [LIME, dict(c="#8E9099", rough=0.62, wrap=0.2, noise=0.05, nfreq=30)]


def controls():
    hw = 1.07
    s = 400 / (2 * hw) / r2.K
    for name, fn, mats, hc in (("c-dpad", dpad, DPAD, 0.25), ("gb-button", gb_button, GB_BUTTON, 0.25), ("gb-pill", gb_pill, GB_PILL, 0.15)):
        cz = -r2.TILT * hc
        r2.render(name, fn, mats, s, 0, ground=0.0, canvas=(-hw, hw, cz - hw, cz + hw), shadow_strength=0.6)


def sheet(names):
    S = 3
    tiles = []
    for nm in names:
        fn, mats = OBJ[nm]
        im, off, _ = r2.render("t-" + nm, fn, mats, 40, 0.3 if nm not in ("disco",) else 0)
        tiles.append(im)
    W = sum(t.width for t in tiles) + 20 * (len(tiles) + 1)
    H = max(t.height for t in tiles) + 40
    bg = Image.new("RGBA", (W, H), (14, 74, 44, 255))
    x = 20
    for t in tiles:
        bg.alpha_composite(t, (x, 20))
        x += t.width + 20
    bg.convert("RGB").save(r2.OUT + "sheet.png")
    print("sheet", bg.size)


def layout():
    man = []
    for i, (nm, cx, cy, s, yaw) in enumerate(PLACES):
        fn, mats = OBJ[nm]
        key = f"{i:02d}-{nm}"
        im, (dx, dy), info = r2.render(key, fn, mats, s, math.radians(yaw))
        man.append(dict(key=key, name=nm, left=cx + dx, top=cy + dy, w=im.width / r2.K, h=im.height / r2.K))
        if nm == "googly":
            info_g = info
            for ex in (-0.34, 0.34):
                px, py = r2.project(r2.rot_y(np.array([[ex, 0.18, 0]]), math.radians(yaw))[0], s, info["g"])
                man[-1].setdefault("pupils", []).append((cx + px, cy + py))
        if nm == "fanhousing":
            fan_cx, fan_cy, fan_s = cx, cy, s
    # the fan blades: rendered alone, square, centred on the projected hub so CSS can spin them
    hb = 0.14
    half = 0.72
    cz = -r2.TILT * hb
    im, off, _ = r2.render("fan-blades", fan_blades, FANB, fan_s, 0, ground=0.0, canvas=(-half, half, cz - half, cz + half), shadow=False)
    man.append(dict(key="fan-blades", name="fan-blades", left=fan_cx - half * fan_s, top=fan_cy + (cz - half) * fan_s, w=im.width / r2.K, h=im.height / r2.K, overlay=True))
    json.dump(man, open(r2.OUT + "manifest.json", "w"), indent=1)
    print("manifest", len(man))


if __name__ == "__main__":
    if sys.argv[1] == "sheet":
        sheet(sys.argv[2:] or list(OBJ))
    elif sys.argv[1] == "layout":
        layout()
    elif sys.argv[1] == "controls":
        controls()
