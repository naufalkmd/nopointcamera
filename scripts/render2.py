"""SDF renderer v2 for the nopointcam board parts (no AI).

What changed from render_objects.py:
- one shared oblique camera for every part: tops keep their true shape (so they sit flat on the flat
  board drawing) and fronts show at TILT of their height, so all parts read from the same viewpoint
- one studio: a soft key from the screen's top-left, a front fill card, a magenta strip and a lime
  kicker (the console's neon), a green bounce from the board, so metals and glossy plastic reflect
  something instead of looking grey
- split-sum style specular with roughness, clearcoat, wrap diffuse for candy/rubber
- procedural texture hooks (albedo, roughness, bump) plus value-noise micro variation
- contact shadow + ambient occlusion baked onto a transparent ground, in board coordinates
"""
import math
import time

import os

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "parts") + "/"
TILT = 0.4            # how far up the screen a point moves per unit of height
K, SS = 2, 2          # board px per CSS px, supersampling factor
EXPOSURE = 1.1


def nz(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


L = nz([-0.5, 1.0, -0.42])                 # key light, from the screen's top-left
VIEW = nz([0.0, -1.0, -TILT])              # every ray is parallel (oblique projection)
KEY_E = 2.6
KEY_COL = np.array([1.0, 0.95, 0.88])
KEY_RHO = 0.27                             # softbox angular radius
LOBES = [                                  # direction, cosine power, radiance
    (nz([0, 1, 0]), 1.5, np.array([0.32, 0.35, 0.41])),        # soft dome
    (nz([-0.6, 0.65, -0.8]), 40.0, np.array([0.4, 1.7, 2.6])), # cyan strip, left-back (the LED strip)
    (nz([0.2, 0.5, 1.0]), 3.0, np.array([0.5, 0.5, 0.52])),    # big front fill card
    (nz([1.0, 0.32, -0.45]), 36.0, np.array([2.8, 0.8, 2.3])), # magenta strip, right-back
    (nz([-1.0, 0.3, 0.5]), 24.0, np.array([1.1, 1.7, 0.35])),  # lime kicker, left-front
    (nz([0, -1, 0]), 1.0, np.array([0.03, 0.15, 0.08])),       # green board bounce
]


# ---------------- helpers ----------------

def srgb2lin(h):
    h = h.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rot_y(p, a):
    c, s = math.cos(a), math.sin(a)
    return np.stack([c * p[:, 0] + s * p[:, 2], p[:, 1], -s * p[:, 0] + c * p[:, 2]], 1)


def _hash(ix, iy, iz, seed=0):
    h = (ix * 374761393 + iy * 668265263 + iz * 1274126177 + seed * 144665) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 4294967295.0


def vnoise(p, seed=0):
    f = np.floor(p)
    t = p - f
    i = f.astype(np.int64)
    u = t * t * (3 - 2 * t)
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                out = out + w * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def fbm(p, octaves=4, seed=0):
    a, tot, s = 0.5, 0.0, 0.0
    for o in range(octaves):
        s = s + a * vnoise(p * (2 ** o), seed + o)
        tot += a
        a *= 0.5
    return s / tot


def cell_rand(ids, seed=0):
    """Stable random number per integer cell id (N x k int array)."""
    ids = np.asarray(ids, np.int64)
    z = np.zeros(len(ids), np.int64)
    cols = [ids[:, i] if ids.shape[1] > i else z for i in range(3)]
    return _hash(cols[0], cols[1], cols[2], seed)


def tex_sample(img, u, v):
    """Bilinear sample of an HxWxC float array at u,v in [0,1] (v down)."""
    H, W = img.shape[:2]
    x = np.clip(u, 0, 1) * (W - 1)
    y = np.clip(v, 0, 1) * (H - 1)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = np.minimum(x0 + 1, W - 1)
    y1 = np.minimum(y0 + 1, H - 1)
    fx = (x - x0)[:, None]
    fy = (y - y0)[:, None]
    a = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    b = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return a * (1 - fy) + b * fy


def bounds(obj, lim=1.8, n=72):
    g = np.linspace(-lim, lim, n)
    X, Y, Zg = np.meshgrid(g, g, g, indexing="ij")
    p = np.stack([X.ravel(), Y.ravel(), Zg.ravel()], 1)
    d = obj(p)[0]
    step = g[1] - g[0]
    inside = d < step * 0.2
    q = p[inside]
    lo, hi = q.min(0), q.max(0)
    # refine the floor: march straight down on a coarse xz grid to find the true lowest point
    return lo - step * 0.5, hi + step * 0.5


# ---------------- lighting ----------------

def env_spec(R, rough, key_vis):
    """Pre-blurred environment radiance in direction R for GGX-ish roughness."""
    a = np.maximum(rough, 0.03) ** 2
    n_a = 2.0 / (a * a) - 2.0
    col = np.zeros((len(R), 3))
    for d, n, I in LOBES:
        ne = n * n_a / (n + n_a)
        c = np.clip(R @ d, 0, 1)
        col += ((ne + 1) / (n + 1) * c ** ne)[:, None] * I[None, :]
    # key softbox: a disc that widens and dims with roughness
    th = np.arccos(np.clip(R @ L, -1, 1))
    beta = np.maximum(rough, 0.03) ** 2 * 1.6 + 0.01
    w = np.clip((KEY_RHO + beta - th) / (2 * beta + 0.02), 0, 1)
    w = w * w * (3 - 2 * w)
    I_k = KEY_E / (math.pi * KEY_RHO ** 2)
    col += (I_k * KEY_RHO ** 2 / (KEY_RHO ** 2 + beta ** 2) * w * key_vis)[:, None] * KEY_COL[None, :]
    return col


def env_irr(n):
    E = np.zeros((len(n), 3))
    for d, pw, I in LOBES:
        P = I * 2 * math.pi / (pw + 1)
        w = 1.0 / (pw + 1)
        E += np.clip((n @ d + w) / (1 + w), 0, 1)[:, None] * P[None, :]
    return E


def env_brdf(F0, rough, NoV):
    c0 = np.array([-1.0, -0.0275, -0.572, 0.022])
    c1 = np.array([1.0, 0.0425, 1.04, -0.04])
    r = rough[:, None] * c0[None, :] + c1[None, :]
    a004 = np.minimum(r[:, 0] ** 2, np.exp2(-9.28 * NoV)) * r[:, 0] + r[:, 1]
    A = a004 * -1.04 + r[:, 2]
    B = a004 * 1.04 + r[:, 3]
    return F0 * A[:, None] + B[:, None]


def smooth01(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def aces(x):
    return np.clip(x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


# ---------------- render ----------------

def render(name, obj, mats, s, yaw=0.0, ground=None, canvas=None, shadow=True, save=True, shadow_strength=0.85):
    """Render obj (local units, y up) standing on the board.

    s: CSS px per unit. yaw: rotation about the vertical axis (radians, counter-clockwise seen from above).
    Returns (RGBA uint8 image at K px per CSS px, (dx, dy) CSS offset of the sprite's top-left from
    the object's origin on the board)."""
    t0 = time.time()
    lo, hi = bounds(obj)
    g = lo[1] if ground is None else ground
    Htop = hi[1] - g
    scene = (lambda p: obj(rot_y(p, -yaw))) if yaw else obj
    cr = np.array([[x, 0, z] for x in (lo[0], hi[0]) for z in (lo[2], hi[2])])
    cw = rot_y(cr, yaw)
    x0, x1 = cw[:, 0].min(), cw[:, 0].max()
    z0, z1 = cw[:, 2].min(), cw[:, 2].max()
    sx, sz = -L[0] / L[1], -L[2] / L[1]    # shadow displacement per unit height
    m = 0.14
    if canvas is None:
        X0, X1 = x0 - m, x1 + max(sx, 0) * Htop * 1.25 + m + 0.08
        Z0, Z1 = z0 - TILT * Htop - m, z1 + max(sz, 0) * Htop * 1.25 + m + 0.08
    else:
        X0, X1, Z0, Z1 = canvas
    ppu = s * K * SS
    Wp = int(math.ceil((X1 - X0) * s * K)) * SS
    Hp = int(math.ceil((Z1 - Z0) * s * K)) * SS
    X1 = X0 + Wp / ppu
    Z1 = Z0 + Hp / ppu
    js, is_ = np.meshgrid(np.arange(Wp), np.arange(Hp))
    gx = X0 + (js.ravel() + 0.5) / ppu
    gz = Z0 + (is_.ravel() + 0.5) / ppu
    N = gx.size
    Y = Htop + 0.25
    O = np.stack([gx, np.full(N, g + Y), gz + TILT * Y], 1)
    D = VIEW
    Tg = Y * math.sqrt(1 + TILT * TILT)

    # cull rays that miss the bounding sphere
    cen = rot_y(((lo + hi) / 2)[None, :], yaw)[0]
    rad = np.linalg.norm(hi - lo) / 2 + 0.02
    oc = O - cen
    b = oc @ D
    c = np.einsum("ij,ij->i", oc, oc) - rad * rad
    disc = b * b - c
    near = disc > 0
    t = np.where(near, np.maximum(-b - np.sqrt(np.maximum(disc, 0)), 0), Tg)
    hit = np.zeros(N, bool)
    act = np.nonzero(near)[0]
    eps = 0.3 / ppu
    for _ in range(260):
        if act.size == 0:
            break
        p = O[act] + D * t[act, None]
        d = scene(p)[0]
        t[act] += d * 0.9
        done = d < eps
        hit[act[done]] = True
        act = act[(~done) & (t[act] < Tg)]
    hit &= t < Tg

    rgb = np.zeros((N, 3))
    alpha = np.zeros(N)

    # ---- object shading ----
    idx = np.nonzero(hit)[0]
    if idx.size:
        p = O[idx] + D * t[idx, None]
        _d, mid = scene(p)
        e = max(0.4 / ppu, 0.0007)
        n = np.zeros_like(p)
        for k in np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], float):
            n += k[None, :] * scene(p + k[None, :] * e)[0][:, None]
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        q = rot_y(p, -yaw) if yaw else p
        nl = rot_y(n, -yaw) if yaw else n

        # bump + per-material normal hooks (evaluated in local space)
        for mi, mt in enumerate(mats):
            sel = mid == mi
            if not sel.any():
                continue
            if "normal_fn" in mt:
                nn = mt["normal_fn"](q[sel], nl[sel])
                n[sel] = rot_y(nn, yaw) if yaw else nn
            if "bump_fn" in mt:
                bf, amt = mt["bump_fn"], mt.get("bump", 1.0)
                qs = q[sel]
                eb = 0.004
                grad = np.stack([(bf(qs + [eb, 0, 0]) - bf(qs - [eb, 0, 0])),
                                 (bf(qs + [0, eb, 0]) - bf(qs - [0, eb, 0])),
                                 (bf(qs + [0, 0, eb]) - bf(qs - [0, 0, eb]))], 1) / (2 * eb)
                gw = rot_y(grad, yaw) if yaw else grad
                ns = n[sel]
                gt = gw - ns * np.sum(gw * ns, 1, keepdims=True)
                ns = ns - amt * gt
                n[sel] = ns / np.linalg.norm(ns, axis=1, keepdims=True)

        # soft shadow toward the key
        sh = np.ones(len(idx))
        tt = np.full(len(idx), 0.02)
        o = p + n * 0.006
        for _ in range(56):
            dd = scene(o + L[None, :] * tt[:, None])[0]
            sh = np.minimum(sh, 10 * dd / tt)
            tt += np.clip(dd, 0.008, 0.15)
            if tt.min() > 3:
                break
        sh = np.clip(sh, 0, 1)
        sh = sh * sh * (3 - 2 * sh)
        # ambient occlusion, including the board under the part
        ao = np.zeros(len(idx))
        for i, hh in enumerate([0.02, 0.05, 0.1, 0.18, 0.3]):
            pp = p + n * hh
            dd = np.minimum(scene(pp)[0], pp[:, 1] - g)
            ao += np.maximum(hh - dd, 0) * (0.72 ** i)
        ao = np.clip(1 - 1.7 * ao, 0, 1)

        V = -D
        NoV = np.clip(n @ V, 1e-3, 1)
        R = 2 * NoV[:, None] * n - V[None, :]
        E = env_irr(n)
        col = np.zeros((len(idx), 3))
        for mi, mt in enumerate(mats):
            sel = mid == mi
            if not sel.any():
                continue
            qs, ns = q[sel], n[sel]
            alb = np.tile(srgb2lin(mt["c"]), (sel.sum(), 1))
            fq = mt.get("nfreq", 9.0)
            nv = mt.get("noise", 0.05)
            if nv:
                alb *= (1 + nv * (fbm(qs * fq, 3, 7 + mi) - 0.5) * 2)[:, None]
            if "albedo_fn" in mt:
                alb = mt["albedo_fn"](qs, nl[sel], alb)
            rough = np.full(sel.sum(), float(mt.get("rough", 0.4)))
            rn = mt.get("rnoise", 0.12)
            if rn:
                rough = rough + rn * (fbm(qs * fq * 1.7, 3, 31 + mi) - 0.5) * 2
            if "rough_fn" in mt:
                rough = mt["rough_fn"](qs, nl[sel], rough)
            rough = np.clip(rough, 0.03, 1)
            metal = float(mt.get("metal", 0))
            wrap = mt.get("wrap", 0.0)
            ndl = np.clip((ns @ L + wrap) / (1 + wrap), 0, 1)
            F0 = 0.04 * (1 - metal) + alb * metal
            spec_occ = np.clip(ao[sel] ** 0.6, 0, 1)
            key_vis = 0.2 + 0.8 * sh[sel]
            spec = env_spec(R[sel], rough, key_vis) * env_brdf(F0, rough, NoV[sel]) * spec_occ[:, None]
            diff = alb * (1 - metal) / math.pi * (E[sel] * ao[sel, None] + KEY_E * KEY_COL[None, :] * (ndl * sh[sel])[:, None])
            if wrap:
                # light that soaks into candy/rubber: warm the shadow side with the saturated albedo
                diff += alb ** 1.6 * (1 - metal) * wrap * 0.22 * KEY_E * (1 - sh[sel])[:, None] * ao[sel, None]
            c = diff + spec
            coat = mt.get("coat", 0.0)
            if coat:
                Fc = 0.04 + 0.96 * (1 - NoV[sel]) ** 5
                cs = env_spec(R[sel], np.full(sel.sum(), mt.get("coat_rough", 0.06)), key_vis) * spec_occ[:, None]
                c = c * (1 - coat * Fc)[:, None] + coat * Fc[:, None] * cs
            em = mt.get("emit", 0.0)
            if em:
                c += alb * em
            if "emit_fn" in mt:
                c += mt["emit_fn"](qs, nl[sel], alb)
            col[sel] = c
        rgb[idx] = lin2srgb(aces(col * EXPOSURE))
        alpha[idx] = 1

    # ---- contact shadow on the ground ----
    if shadow:
        gi = np.nonzero(~hit)[0]
        G = np.stack([gx[gi], np.full(gi.size, g), gz[gi]], 1)
        # only points that could be shadowed: near the part or along the light direction from it
        rel = G - cen
        along = -(rel[:, 0] * L[0] + rel[:, 2] * L[2]) / math.hypot(L[0], L[2])
        dist = np.hypot(rel[:, 0], rel[:, 2])
        cand = dist < rad * 1.3 + Htop * 1.3
        gi2 = gi[cand]
        G = G[cand]
        shg = np.ones(len(gi2))
        tt = np.full(len(gi2), 0.01)
        for _ in range(64):
            dd = scene(G + L[None, :] * tt[:, None])[0]
            shg = np.minimum(shg, 6 * dd / tt)
            tt += np.clip(dd, 0.01, 0.2)
        shg = np.clip(shg, 0, 1)
        aog = np.zeros(len(gi2))
        for i, hh in enumerate([0.015, 0.04, 0.09, 0.18, 0.32]):
            aog += np.maximum(hh - scene(G + np.array([0, hh, 0]))[0], 0) * (0.8 ** i)
        aog = np.clip(1 - 2.2 * aog, 0, 1)
        a = np.clip((0.62 * (1 - shg) + 0.95 * (1 - aog)) * shadow_strength, 0, 0.9)
        # fade out toward the sprite border so a tight canvas never shows a hard shadow edge
        ex = np.minimum(G[:, 0] - X0, X1 - G[:, 0]) / (X1 - X0)
        ez = np.minimum(G[:, 2] - Z0, Z1 - G[:, 2]) / (Z1 - Z0)
        a = a * smooth01(np.minimum(ex, ez) / 0.08)
        alpha[gi2] = a
        rgb[gi2] = np.array([0.0, 0.035, 0.02])

    img = np.concatenate([rgb, alpha[:, None]], 1).reshape(Hp, Wp, 4)
    pm = img.copy()
    pm[..., :3] *= pm[..., 3:4]
    pm = pm.reshape(Hp // SS, SS, Wp // SS, SS, 4).mean((1, 3))
    a = pm[..., 3:4]
    out = np.concatenate([np.where(a > 0, pm[..., :3] / np.maximum(a, 1e-6), 0), a], -1)
    im = Image.fromarray((out * 255 + 0.5).clip(0, 255).astype(np.uint8), "RGBA")
    if save:
        im.save(OUT + name + ".png", optimize=True)
    off = (X0 * s, Z0 * s)
    print(f"{name}: {Wp // SS}x{Hp // SS}px  hit {idx.size}  {time.time() - t0:.1f}s", flush=True)
    return im, off, dict(g=g, X0=X0, Z0=Z0, s=s)


def project(pt, s, g):
    """Board CSS offset of a local 3D point (already yawed) relative to the object's origin."""
    x, y, z = pt
    return x * s, (z - TILT * (y - g)) * s
