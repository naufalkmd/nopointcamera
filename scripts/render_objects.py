"""Tiny numpy SDF ray-marcher: renders glossy toy-like 3D objects to transparent PNGs."""
import math
import sys
import time

import os

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out") + "/"
RES = (800, 400)   # render size, output size (2x supersampled)


def srgb2lin(h):
    h = h.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def length(v):
    return np.sqrt(np.einsum("ij,ij->i", v, v))


def len2(x, y):
    return np.sqrt(x * x + y * y)


def rot(p, axis, a):
    c, s = math.cos(a), math.sin(a)
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    if axis == "x":
        return np.stack([x, c * y - s * z, s * y + c * z], 1)
    if axis == "y":
        return np.stack([c * x + s * z, y, -s * x + c * z], 1)
    return np.stack([c * x - s * y, s * x + c * y, z], 1)


def sphere(p, c, r):
    return length(p - np.asarray(c, float)) - r


def rcyl(p, rad, h, rb):
    dx = len2(p[:, 0], p[:, 2]) - (rad - rb)
    dy = np.abs(p[:, 1]) - (h - rb)
    return np.minimum(np.maximum(dx, dy), 0) + len2(np.maximum(dx, 0), np.maximum(dy, 0)) - rb


def torus(p, big, r):
    q = len2(p[:, 0], p[:, 2]) - big
    return len2(q, p[:, 1]) - r


def rbox(p, b, r):
    q = np.abs(p) - (np.asarray(b, float) - r)
    return length(np.maximum(q, 0)) + np.minimum(q.max(1), 0) - r


def capsule(p, a, b, r):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    pa = p - a
    ba = b - a
    h = np.clip(pa @ ba / (ba @ ba), 0, 1)
    return length(pa - h[:, None] * ba) - r


def ellipsoid(p, c, rad):
    q = p - np.asarray(c, float)
    rad = np.asarray(rad, float)
    k0 = length(q / rad)
    k1 = length(q / (rad * rad))
    return k0 * (k0 - 1) / np.maximum(k1, 1e-6)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)


def extrude(d2, z, hz, rb):
    dz = np.abs(z) - hz
    return np.minimum(np.maximum(d2, dz), 0) + len2(np.maximum(d2, 0), np.maximum(dz, 0)) - rb


def U(d, m, d2, m2):
    s = d2 < d
    return np.where(s, d2, d), np.where(s, m2, m)


def tri2d(x, y, r):
    k = math.sqrt(3)
    x = np.abs(x) - r
    y = y + r / k
    cond = x + k * y > 0
    x2 = np.where(cond, (x - k * y) / 2, x)
    y2 = np.where(cond, (-k * x - y) / 2, y)
    x2 = x2 - np.clip(x2, -2 * r, 0)
    return -len2(x2, y2) * np.sign(y2)


def star2d(x, y, r, rf):
    k1x, k1y = 0.809016994375, -0.587785252292
    k2x, k2y = -k1x, k1y
    x = np.abs(x)
    dt = np.maximum(k1x * x + k1y * y, 0)
    x, y = x - 2 * dt * k1x, y - 2 * dt * k1y
    dt = np.maximum(k2x * x + k2y * y, 0)
    x, y = x - 2 * dt * k2x, y - 2 * dt * k2y
    x = np.abs(x)
    y = y - r
    bax, bay = rf * -k1y, rf * k1x - 1
    h = np.clip((x * bax + y * bay) / (bax * bax + bay * bay), 0, r)
    return len2(x - bax * h, y - bay * h) * np.sign(y * bax - x * bay)


def poly2d(x, y, pts):
    v = np.asarray(pts, float)
    d = (x - v[0, 0]) ** 2 + (y - v[0, 1]) ** 2
    s = np.ones_like(x)
    n = len(v)
    for i in range(n):
        j = (i - 1) % n
        ex, ey = v[j, 0] - v[i, 0], v[j, 1] - v[i, 1]
        wx, wy = x - v[i, 0], y - v[i, 1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0, 1)
        bx, by = wx - ex * t, wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = y >= v[i, 1]
        c2 = y < v[j, 1]
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


Z = lambda p: np.zeros(len(p), int)


# ---------- objects ----------

def panic(p):
    d = rbox(p - [0, -0.45, 0], [0.88, 0.2, 0.88], 0.14)
    m = Z(p)
    stripe = (np.floor((p[:, 0] - p[:, 1] + p[:, 2]) * 5.5) % 2 == 0) & (p[:, 1] < -0.33)
    m = np.where(stripe, 1, m)
    d, m = U(d, m, rcyl(p - [0, -0.2, 0], 0.68, 0.07, 0.03), 1)
    dome = np.maximum(sphere(p, [0, -0.36, 0], 0.68), -(p[:, 1] + 0.13))
    dome = smin(dome, torus(p - [0, -0.12, 0], 0.62, 0.065), 0.05)
    d, m = U(d, m, dome, 2)
    return d, m


PANIC = [{"c": "#FFC21A", "spec": 0.35, "shin": 30}, {"c": "#1E1E24", "spec": 0.5, "shin": 60},
         {"c": "#F0261D", "spec": 1.0, "shin": 110, "rim": 0.3}]


def gamepad(p):
    d = rcyl(p - [0, -0.42, 0], 0.95, 0.1, 0.06)
    m = Z(p)
    d, m = U(d, m, rcyl(p - [0, -0.14, 0], 0.66, 0.2, 0.15), 1)
    tr = np.abs(tri2d(p[:, 0], -p[:, 2] + 0.03, 0.26)) - 0.05
    sym = extrude(tr, p[:, 1] - 0.075, 0.045, 0.012)
    d, m = U(d, m, sym, 2)
    return d, m


GAMEPAD = [{"c": "#2A2B33", "spec": 0.4, "shin": 40}, {"c": "#3B3F4C", "spec": 1.0, "shin": 120},
           {"c": "#27D3A2", "spec": 0.6, "shin": 60, "emit": 0.35}]


def bulb(p):
    glass = smin(sphere(p, [0, 0.24, 0], 0.55), capsule(p, [0, -0.28, 0], [0, 0.0, 0], 0.25), 0.22)
    glass = np.maximum(glass, -(p[:, 1] + 0.28))
    d = glass
    m = Z(p)
    rr = len2(p[:, 0], p[:, 2]) - (0.27 + 0.022 * np.sin(p[:, 1] * 50))
    dy = np.abs(p[:, 1] + 0.44) - 0.16
    base = (np.minimum(np.maximum(rr, dy), 0) + len2(np.maximum(rr, 0), np.maximum(dy, 0))) * 0.8 - 0.01
    d, m = U(d, m, base, 1)
    d, m = U(d, m, sphere(p, [0, -0.62, 0], 0.13), 2)
    return d, m


BULB = [{"c": "#FFD35C", "spec": 1.0, "shin": 120, "emit": 1.0, "rim": 0.6},
        {"c": "#C7CBD6", "spec": 1.0, "shin": 70, "metal": True}, {"c": "#2A2A30", "spec": 0.4, "shin": 30}]

_rng = np.random.default_rng(5)
SPRINKLES = []
for _i in range(34):
    a = _rng.uniform(0, 2 * np.pi)
    ph = _rng.uniform(0.3, 1.35)
    c = np.array([(0.55 + 0.335 * np.cos(ph)) * np.cos(a), 0.335 * np.sin(ph), (0.55 + 0.335 * np.cos(ph)) * np.sin(a)])
    nrm = np.array([np.cos(ph) * np.cos(a), np.sin(ph), np.cos(ph) * np.sin(a)])
    rv = _rng.normal(size=3)
    td = rv - nrm * (rv @ nrm)
    td /= np.linalg.norm(td)
    SPRINKLES.append((c - td * 0.05, c + td * 0.05, _i % 4))


def donut(p):
    q = rot(p, "x", -0.55)
    d = torus(q, 0.55, 0.3)
    m = Z(p)
    ang = np.arctan2(q[:, 2], q[:, 0])
    ic = np.maximum(torus(q, 0.55, 0.322), -(q[:, 1] - 0.02 + 0.07 * np.sin(ang * 7) + 0.03 * np.sin(ang * 13 + 1)))
    d, m = U(d, m, ic, 1)
    near = ic < 0.12
    sd = ic - 0.08
    sm = np.full(len(p), 2)
    if near.any():
        qn = q[near]
        ds = np.full(len(qn), 1e3)
        ms = np.full(len(qn), 2)
        for a_, b_, ci in SPRINKLES:
            dc = capsule(qn, a_, b_, 0.022)
            s = dc < ds
            ds = np.where(s, dc, ds)
            ms = np.where(s, 2 + ci, ms)
        sd[near] = ds
        sm[near] = ms
    d, m = U(d, m, sd, sm)
    return d, m


DONUT = [{"c": "#E3A35C", "spec": 0.25, "shin": 20}, {"c": "#FF6FAE", "spec": 0.8, "shin": 70},
         {"c": "#FFD21E", "spec": 0.5, "shin": 50}, {"c": "#FFFFFF", "spec": 0.5, "shin": 50},
         {"c": "#3D7BFF", "spec": 0.5, "shin": 50}, {"c": "#3CE0B0", "spec": 0.5, "shin": 50}]

PIPS = []
_a = 0.27
_pat = {1: [(0, 0)], 2: [(-_a, -_a), (_a, _a)], 3: [(-_a, -_a), (0, 0), (_a, _a)],
        4: [(-_a, -_a), (-_a, _a), (_a, -_a), (_a, _a)], 5: [(-_a, -_a), (-_a, _a), (_a, -_a), (_a, _a), (0, 0)],
        6: [(-_a, -_a), (-_a, 0), (-_a, _a), (_a, -_a), (_a, 0), (_a, _a)]}
for axis, sign, n in [(1, 1, 5), (1, -1, 2), (2, 1, 3), (2, -1, 4), (0, 1, 6), (0, -1, 1)]:
    for u, v in _pat[n]:
        c = [0.0, 0.0, 0.0]
        c[axis] = 0.61 * sign
        others = [i for i in range(3) if i != axis]
        c[others[0]] = u
        c[others[1]] = v
        PIPS.append(c)


def dice(p):
    q = rot(rot(p, "y", 0.62), "x", 0.45)
    box = rbox(q, [0.55, 0.55, 0.55], 0.13)
    dp = np.full(len(p), 1e3)
    for c in PIPS:
        dp = np.minimum(dp, sphere(q, c, 0.105))
    d = np.maximum(box, -dp)
    m = np.where(np.abs(dp) < 0.012, 1, 0)
    return d, m


DICE = [{"c": "#FF3B3B", "spec": 1.0, "shin": 110, "rim": 0.35}, {"c": "#FFFFFF", "spec": 0.4, "shin": 40}]


def cherries(p):
    d = np.minimum(sphere(p, [-0.33, -0.3, 0.12], 0.37), sphere(p, [0.34, -0.36, -0.05], 0.37))
    m = Z(p)
    st = np.minimum.reduce([
        capsule(p, [-0.31, 0.03, 0.1], [-0.2, 0.4, 0.05], 0.032),
        capsule(p, [-0.2, 0.4, 0.05], [0.02, 0.66, 0], 0.032),
        capsule(p, [0.33, -0.03, -0.05], [0.24, 0.36, -0.02], 0.032),
        capsule(p, [0.24, 0.36, -0.02], [0.02, 0.66, 0], 0.032)])
    d, m = U(d, m, st, 1)
    leaf = ellipsoid(rot(p - [0.24, 0.7, 0.02], "z", -0.3), [0, 0, 0], [0.24, 0.05, 0.12])
    d, m = U(d, m, leaf, 2)
    return d, m


CHERRIES = [{"c": "#D9102B", "spec": 1.0, "shin": 110, "rim": 0.3}, {"c": "#6B7F2A", "spec": 0.2, "shin": 20},
            {"c": "#34B04A", "spec": 0.5, "shin": 40}]


def ball(p):
    d = sphere(p, [0, 0, 0], 0.66)
    q = rot(rot(p, "x", -0.95), "z", 0.3)
    ang = np.arctan2(q[:, 2], q[:, 0])
    m = (np.floor((ang + np.pi) / (2 * np.pi) * 6).astype(int)) % 6
    m = np.where(np.abs(q[:, 1]) > 0.57, 6, m)
    return d, m


BALL = [{"c": c, "spec": 0.7, "shin": 70} for c in ["#FF3B30", "#FFC21A", "#2F6BFF", "#FFFFFF", "#27C46B", "#FF7A1A", "#FFFFFF"]]


def duck(p):
    q = rot(p, "y", -0.55)
    body = ellipsoid(q, [0, -0.22, 0], [0.62, 0.36, 0.46])
    tail = ellipsoid(rot(q - [-0.52, -0.02, 0], "z", -0.6), [0, 0, 0], [0.22, 0.1, 0.16])
    b = smin(body, tail, 0.12)
    b = smin(b, sphere(q, [0.26, 0.3, 0], 0.3), 0.14)
    wing = np.minimum(ellipsoid(q, [-0.05, -0.12, 0.42], [0.3, 0.15, 0.08]), ellipsoid(q, [-0.05, -0.12, -0.42], [0.3, 0.15, 0.08]))
    b = smin(b, wing, 0.05)
    d = b
    m = Z(p)
    d, m = U(d, m, ellipsoid(q, [0.58, 0.24, 0], [0.2, 0.065, 0.14]), 1)
    eyes = np.minimum(sphere(q, [0.47, 0.39, 0.17], 0.045), sphere(q, [0.47, 0.39, -0.17], 0.045))
    d, m = U(d, m, eyes, 2)
    return d, m


DUCK = [{"c": "#FFD21E", "spec": 0.8, "shin": 80}, {"c": "#FF7A1A", "spec": 0.7, "shin": 60},
        {"c": "#141418", "spec": 1.0, "shin": 120}]

BOLT = [(0.18, 0.78), (-0.36, -0.04), (-0.02, -0.04), (-0.2, -0.78), (0.38, 0.1), (0.04, 0.1)]


def bolt(p):
    q = rot(rot(p, "y", 0.5), "x", -0.2)
    d = extrude(poly2d(q[:, 0], q[:, 1], BOLT) + 0.04, q[:, 2], 0.08, 0.06)
    return d, Z(p)


BOLTM = [{"c": "#FF4B2B", "spec": 1.0, "shin": 100, "rim": 0.3}]


def coin(p):
    q = rot(rot(p, "x", 1.1), "z", 0.35)
    ang = np.arctan2(q[:, 2], q[:, 0])
    rr = len2(q[:, 0], q[:, 2]) - (0.63 + 0.007 * np.sin(ang * 90))
    dy = np.abs(q[:, 1]) - 0.06
    body = np.minimum(np.maximum(rr, dy), 0) + len2(np.maximum(rr, 0), np.maximum(dy, 0)) - 0.03
    d = body
    d = np.minimum(d, torus(q - [0, 0.085, 0], 0.54, 0.03))
    d = np.minimum(d, torus(q - [0, -0.085, 0], 0.54, 0.03))
    st = extrude(star2d(q[:, 0], -q[:, 2], 0.3, 0.45), np.abs(q[:, 1]) - 0.08, 0.02, 0.015)
    d = np.minimum(d, st)
    return d * 0.9, Z(p)


COIN = [{"c": "#FFC83D", "spec": 1.0, "shin": 50, "metal": True, "rim": 0.35}]


def star(p):
    q = rot(rot(p, "y", 0.45), "z", 0.25)
    d = extrude(star2d(q[:, 0], q[:, 1], 0.72, 0.48), q[:, 2], 0.06, 0.13)
    return d, Z(p)


STAR = [{"c": "#8E5CFF", "spec": 1.0, "shin": 100, "rim": 0.35}]


def pill(p):
    q = rot(rot(p, "z", 0.6), "y", 0.5)
    d = capsule(q, [-0.5, 0, 0], [0.5, 0, 0], 0.3)
    m = np.where(q[:, 0] < 0, 0, 1)
    return d, m


PILL = [{"c": "#FF6FAE", "spec": 1.0, "shin": 110}, {"c": "#4C7DFF", "spec": 1.0, "shin": 110}]


# ---------- renderer ----------

def render(name, scene, mats, cam=(0, 1.6, 3.2), target=(0, -0.05, 0), fov=34, normal_hook=None):
    t0 = time.time()
    R, S = RES
    ys, xs = np.mgrid[0:R, 0:R]
    u = ((xs + 0.5) / R * 2 - 1).ravel()
    v = (-((ys + 0.5) / R * 2 - 1)).ravel()
    ro = np.array(cam, float)
    fw = np.array(target, float) - ro
    fw /= np.linalg.norm(fw)
    rt = np.cross(fw, [0, 1, 0])
    rt /= np.linalg.norm(rt)
    up = np.cross(rt, fw)
    tf = math.tan(math.radians(fov / 2))
    rd = fw[None, :] + (u * tf)[:, None] * rt[None, :] + (v * tf)[:, None] * up[None, :]
    rd /= np.linalg.norm(rd, axis=1, keepdims=True)
    N = rd.shape[0]
    t = np.full(N, 1.0)
    hit = np.zeros(N, bool)
    act = np.arange(N)
    for _ in range(180):
        p = ro + rd[act] * t[act, None]
        d, _m = scene(p)
        t[act] += d * 0.85
        done = d < 0.0012
        hit[act[done]] = True
        act = act[(~done) & (t[act] < 9)]
        if act.size == 0:
            break
    idx = np.nonzero(hit)[0]
    p = ro + rd[idx] * t[idx, None]
    _d, m = scene(p)
    e = 0.0015
    n = np.zeros_like(p)
    for k in np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], float):
        n += k[None, :] * scene(p + k[None, :] * e)[0][:, None]
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    if normal_hook is not None:
        n = normal_hook(p, n, m)
    L1 = np.array([-0.55, 0.85, 0.6])
    L1 /= np.linalg.norm(L1)
    L2 = np.array([0.85, 0.25, 0.45])
    L2 /= np.linalg.norm(L2)
    sh = np.ones(len(idx))
    tt = np.full(len(idx), 0.03)
    o = p + n * 0.006
    for _ in range(48):
        dd = scene(o + L1[None, :] * tt[:, None])[0]
        sh = np.minimum(sh, 9 * dd / tt)
        tt += np.clip(dd, 0.01, 0.2)
    sh = np.clip(sh, 0, 1)
    sh = sh * sh * (3 - 2 * sh)
    ao = np.zeros(len(idx))
    for i, hh in enumerate([0.02, 0.06, 0.12, 0.2, 0.3]):
        ao += (hh - scene(p + n * hh)[0]) * (0.75 ** i)
    ao = np.clip(1 - 1.5 * ao, 0, 1)
    V = -rd[idx]
    ndl1 = np.clip(n @ L1, 0, 1)
    ndl2 = np.clip(n @ L2 * 0.5 + 0.5, 0, 1) ** 2
    ndv = np.clip(np.sum(n * V, 1), 0, 1)
    fres = (1 - ndv) ** 4
    H1 = L1[None, :] + V
    H1 /= np.linalg.norm(H1, axis=1, keepdims=True)
    ndh = np.clip(np.sum(n * H1, 1), 0, 1)
    hemi = n[:, 1] * 0.5 + 0.5
    sky = np.array([0.82, 0.86, 1.0])
    gnd = np.array([0.62, 0.5, 0.45])
    col = np.zeros((len(idx), 3))
    for mi, mt in enumerate(mats):
        s = m == mi
        if not s.any():
            continue
        alb = srgb2lin(mt["c"])
        metal = mt.get("metal", False)
        amb = (gnd[None, :] * (1 - hemi[s, None]) + sky[None, :] * hemi[s, None]) * 0.5 * ao[s, None]
        key = np.array([1.0, 0.95, 0.88]) * 1.15 * (ndl1[s] * sh[s])[:, None]
        fill = np.array([0.6, 0.7, 1.0]) * 0.32 * ndl2[s][:, None] * ao[s, None]
        c = (alb * (0.55 if metal else 1.0))[None, :] * (amb + key + fill)
        spec = (ndh[s] ** mt.get("shin", 48)) * mt.get("spec", 0.5) * (0.25 + 0.75 * sh[s])
        c += spec[:, None] * (alb if metal else np.ones(3))[None, :] * 1.5
        c += fres[s, None] * mt.get("rim", 0.22) * np.array([0.92, 0.95, 1.0])[None, :] * ao[s, None]
        if metal:
            c += (np.clip(n[s, 1] * 0.5 + 0.5, 0, 1) ** 2)[:, None] * alb[None, :] * 0.7 * ao[s, None]
        em = mt.get("emit", 0)
        if em:
            c += alb[None, :] * em * (0.5 + 0.5 * ndv[s])[:, None]
        col[s] = c
    col = col / (1 + col * 0.3)
    col = np.clip(col, 0, 1) ** (1 / 2.2)
    img = np.zeros((N, 4))
    img[idx, :3] = col
    img[idx, 3] = 1
    img = img.reshape(R, R, 4)
    pm = img.copy()
    pm[..., :3] *= pm[..., 3:4]
    pm = pm.reshape(S, 2, S, 2, 4).mean((1, 3))
    a = pm[..., 3:4]
    rgb = np.where(a > 0, pm[..., :3] / np.maximum(a, 1e-6), 0)
    out = np.concatenate([rgb, a], -1)
    Image.fromarray((out * 255 + 0.5).clip(0, 255).astype(np.uint8), "RGBA").save(OUT + name + ".png", optimize=True)
    print(name, len(idx), round(time.time() - t0, 1), "s", flush=True)


JOBS = {
    "obj-panic": (panic, PANIC, dict(cam=(0, 2.0, 3.0), target=(0, -0.12, 0))),
    "obj-gamepad": (gamepad, GAMEPAD, dict(cam=(0, 2.1, 2.9), target=(0, -0.15, 0))),
    "obj-bulb": (bulb, BULB, dict(cam=(0.4, 0.7, 3.4), target=(0, 0.0, 0))),
    "obj-donut": (donut, DONUT, dict(cam=(0, 1.9, 2.9), target=(0, -0.05, 0), fov=36)),
    "obj-dice": (dice, DICE, dict(cam=(0, 1.3, 3.3), target=(0, 0, 0))),
    "obj-cherries": (cherries, CHERRIES, dict(cam=(0, 0.6, 3.1), target=(0, 0.1, 0))),
    "obj-ball": (ball, BALL, dict(cam=(0, 0.9, 3.4), target=(0, 0, 0))),
    "obj-duck": (duck, DUCK, dict(cam=(0, 0.9, 3.4), target=(0, 0.0, 0))),
    "obj-bolt": (bolt, BOLTM, dict(cam=(0, 0.4, 3.5), target=(0, 0, 0))),
    "obj-coin": (coin, COIN, dict(cam=(0, 0.6, 3.4), target=(0, 0, 0))),
    "obj-star": (star, STAR, dict(cam=(0, 0.4, 3.5), target=(0, 0, 0))),
    "obj-pill": (pill, PILL, dict(cam=(0, 0.8, 3.4), target=(0, 0, 0))),
}

if __name__ == "__main__":
    names = sys.argv[1:] or list(JOBS)
    for nm in names:
        fn, mats, kw = JOBS[nm]
        render(nm, fn, mats, **kw)
