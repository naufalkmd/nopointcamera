// The whole FILTERS.md pipeline as one Skia shader (SkSL), run on the GPU:
// grade and tone -> one wild effect -> optics -> film texture. Framing (tilt, the print)
// happens in the React Native views around it.
import { STOCKS, PALETTES, WILDS, type Recipe } from './recipe';

export const DEVELOP_SKSL = `
uniform shader image;
uniform float2 res;
uniform float seed;

uniform float3 mixR;
uniform float3 mixG;
uniform float3 mixB;
uniform float mono;
uniform float contrast;
uniform float gamma;
uniform float sat;
uniform float lift;
uniform float3 shadowTint;
uniform float3 highTint;
uniform float lutMix;

uniform float exposure;
uniform float temp;
uniform float tint;

uniform float wType;
uniform float wAmt;
uniform float4 wP;
uniform float3 pal0;
uniform float3 pal1;
uniform float3 pal2;
uniform float3 pal3;
uniform float3 pal4;

uniform float vignette;
uniform float soft;
uniform float fringe;
uniform float dbl;
uniform float4 dblT;

uniform float grain;
uniform float halation;
uniform float leak;
uniform float2 leakPos;
uniform float3 leakCol;
uniform float dust;

const float3 PAPER = float3(0.95, 0.93, 0.88);

float luma(float3 c) { return dot(c, float3(0.2126, 0.7152, 0.0722)); }

float hash(float2 p) {
  float3 p3 = fract(float3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

bool isWild(float k) { return abs(wType - k) < 0.5; }

// Stage 1 and 2: the film grade and the tone.
float3 grade(float3 c) {
  float3 o = c;
  c = float3(dot(c, mixR), dot(c, mixG), dot(c, mixB));
  if (mono > 0.5) c = float3(luma(c));
  c *= exp2(exposure);
  c *= float3(1.0 + temp * 0.08 + tint * 0.03, 1.0 - tint * 0.06, 1.0 - temp * 0.08 + tint * 0.03);
  c = clamp(c, 0.0, 1.0);
  c = mix(c, c * c * (3.0 - 2.0 * c), contrast);
  c = pow(max(c, float3(0.0)), float3(gamma));
  float l = luma(c);
  c += shadowTint * (1.0 - smoothstep(0.0, 0.5, l));
  c *= mix(float3(1.0), highTint, smoothstep(0.5, 1.0, l));
  l = luma(c);
  c = mix(float3(l), c, sat);
  c = c * (1.0 - lift) + lift;
  c = clamp(c, 0.0, 1.0);
  return mix(o, c, lutMix);
}

float3 develop(float2 q) { return grade(image.eval(q).rgb); }

float3 ramp(float t) {
  t = clamp(t, 0.0, 1.0) * 4.0;
  if (t < 1.0) return mix(pal0, pal1, t);
  if (t < 2.0) return mix(pal1, pal2, t - 1.0);
  if (t < 3.0) return mix(pal2, pal3, t - 2.0);
  return mix(pal3, pal4, t - 3.0);
}

float2 rotate(float2 v, float a) {
  float c = cos(a);
  float s = sin(a);
  return float2(c * v.x - s * v.y, s * v.x + c * v.y);
}

float bayer2(float x, float y) {
  if (x < 0.5) return y < 0.5 ? 0.0 : 3.0;
  return y < 0.5 ? 2.0 : 1.0;
}

float bayer4(float2 cell) {
  float2 a = mod(cell, 2.0);
  float2 b = floor(mod(cell, 4.0) / 2.0);
  return (4.0 * bayer2(a.x, a.y) + bayer2(b.x, b.y)) / 16.0;
}

half4 main(float2 p) {
  float2 q = p;
  float2 center = wP.xy * res;

  // Wild effects that bend the geometry.
  if (isWild(7.0)) {
    float2 d = q - center;
    float r = length(d);
    float seg = 6.2831853 / wP.z;
    float a = mod(atan(d.y, d.x), seg);
    a = abs(a - seg * 0.5);
    q = center + r * float2(cos(a), sin(a));
  }
  if (isWild(8.0)) {
    float2 d = q - center;
    float t = clamp(1.0 - length(d) / (res.x * 0.65), 0.0, 1.0);
    q = center + rotate(d, t * t * wAmt * 5.0);
  }
  float split = 0.0;
  if (isWild(6.0)) {
    float band = floor(p.y / (res.y / 26.0));
    if (hash(float2(band, seed)) > 1.0 - 0.35 * wAmt) q.x += (hash(float2(band + 7.0, seed)) - 0.5) * res.x * 0.22 * wAmt;
    split = res.x * 0.012 * wAmt;
  }

  // The base image, with colour fringing towards the edges.
  float3 col;
  if (fringe > 0.0) {
    float2 off = (q - res * 0.5) / res.x * fringe * res.x * 0.012;
    col = float3(develop(q + off).r, develop(q).g, develop(q - off).b);
  } else {
    col = develop(q);
  }
  if (split > 0.0) {
    col = float3(develop(q + float2(split, 0.0)).r, col.g, develop(q - float2(split, 0.0)).b);
    col *= 0.9 + 0.1 * step(0.5, fract(p.y / 3.0));
  }

  // Double exposure: a shifted, turned, scaled copy, screened on top.
  if (dbl > 0.0) {
    float2 d = rotate(q - res * 0.5, radians(dblT.z)) / dblT.w + res * 0.5 + dblT.xy * res;
    float3 c2 = develop(d);
    col = 1.0 - (1.0 - col) * (1.0 - c2 * dbl);
  }

  // Wild effects that repaint the colour or the pixels.
  if (isWild(1.0)) {
    float cell = res.x / (wAmt > 1.2 ? 96.0 : 128.0);
    float2 ci = floor(p / cell);
    float l = luma(develop((ci + 0.5) * cell));
    float lv = clamp(floor(l * 4.0 + (bayer4(ci) - 0.5) * 1.1), 0.0, 3.0);
    col = lv < 0.5 ? float3(0.059, 0.22, 0.059) : lv < 1.5 ? float3(0.188, 0.384, 0.188) : lv < 2.5 ? float3(0.545, 0.675, 0.059) : float3(0.608, 0.737, 0.059);
  }
  bool legendary = wAmt > 1.2;
  if (isWild(2.0)) {
    // Legendary: the palette repeats in bands.
    float l = luma(col);
    col = mix(col, ramp(legendary ? fract(l * 2.5) : l), clamp(wAmt, 0.0, 1.0));
  }
  if (isWild(3.0)) {
    // Legendary: more levels, cycling through the palette.
    float l = clamp(luma(col), 0.0, 0.999);
    float n = legendary ? mod(floor(l * 7.0), 5.0) : floor(l * 4.0);
    col = n < 0.5 ? pal0 : n < 1.5 ? pal1 : n < 2.5 ? pal2 : n < 3.5 ? pal3 : pal4;
  }
  if (isWild(4.0)) {
    float g = res.x / (wAmt > 1.2 ? 34.0 : 64.0);
    float2 r = rotate(p, 0.785398);
    float2 rc = (floor(r / g) + 0.5) * g;
    float l = luma(develop(rotate(rc, -0.785398)));
    float rad = g * 0.5 * sqrt(1.0 - l) * 1.2;
    float ink = 1.0 - smoothstep(rad - 1.0, rad + 1.0, length(r - rc));
    col = mix(PAPER, pal1 * 0.85, ink);
  }
  if (isWild(5.0)) {
    float2 off = float2(res.x * 0.012, res.x * 0.006) * wAmt;
    float n = hash(floor(p / 1.5) + seed) - 0.5;
    float la = luma(develop(p + off));
    float lb = luma(develop(p - off));
    float ca = smoothstep(0.15, 0.95, 1.0 - la + n * 0.3);
    float cb = smoothstep(0.35, 1.0, 1.0 - lb + n * 0.3);
    col = PAPER * mix(float3(1.0), pal1, ca) * mix(float3(1.0), pal2, cb);
  }
  if (isWild(9.0)) {
    float stride = res.y * 0.012 * wAmt;
    float3 best = col;
    float bl = luma(col);
    for (int i = 1; i < 24; i++) {
      float3 d = develop(q - float2(0.0, float(i) * stride));
      float l = luma(d);
      float w = l * (1.0 - float(i) / 24.0);
      if (l > 0.55 && w > bl) {
        best = d;
        bl = w;
      }
    }
    col = best;
  }
  if (isWild(10.0)) {
    float3 s = wP.w < 0.5 ? col.gbr : col.brg;
    float3 sol = legendary ? 1.0 - abs(2.0 * s - 1.0) : mix(s, 1.0 - s, step(float3(0.55), s));
    col = mix(col, sol, clamp(wAmt, 0.0, 1.0));
  }

  // Stage 4 and 5: softness and halation from a blurred ring around the pixel.
  if (soft > 0.0 || halation > 0.0) {
    float3 blur = float3(0.0);
    float rad = res.x * 0.014;
    for (int i = 0; i < 12; i++) {
      float a = float(i) * 0.5235988;
      float k = mod(float(i), 2.0) < 0.5 ? 1.0 : 0.5;
      blur += image.eval(q + float2(cos(a), sin(a)) * rad * k).rgb;
    }
    blur /= 12.0;
    if (soft > 0.0) col = mix(col, max(col, grade(blur)), soft);
    float hi = max(luma(blur) - 0.62, 0.0) / 0.38;
    col += float3(1.0, 0.32, 0.12) * hi * halation * 0.55;
  }

  float2 uv = p / res;
  float v = length((uv - 0.5) * float2(1.0, res.y / res.x));
  col *= 1.0 - vignette * smoothstep(0.3, 0.85, v);

  if (leak > 0.0) {
    float d = length(p - leakPos * res) / res.x;
    col += leakCol * leak * exp(-d * d * 4.0) * (1.0 - col);
  }

  if (grain > 0.0) {
    float gs = max(res.x / 420.0, 1.0);
    float n = hash(floor(p / gs) + seed) + hash(floor(p / (gs * 2.0)) + seed * 1.3) - 1.0;
    col += n * grain * 0.22 * (1.0 - abs(luma(col) - 0.5));
  }

  if (dust > 0.0) {
    float cs = res.x / 60.0;
    float2 cell = floor(p / cs);
    if (hash(cell + seed * 1.7) > 1.0 - 0.02 * dust) {
      float2 pos = (cell + float2(hash(cell + 3.0), hash(cell + 9.0))) * cs;
      float size = max(res.x / 400.0, 0.8) * (0.6 + hash(cell + 5.0));
      float m = 1.0 - smoothstep(size * 0.5, size, length(p - pos));
      col = mix(col, hash(cell + 11.0) > 0.25 ? float3(0.95) : float3(0.1), m * 0.7);
    }
  }

  return half4(clamp(col, 0.0, 1.0), 1.0);
}
`;

function hex(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

// The shader's inputs for a recipe, in the order they're declared in DEVELOP_SKSL.
export function developUniforms(r: Recipe, width: number, height: number): Record<string, number | number[]> {
  const s = STOCKS[r.stock];
  const mix = 'mix' in s ? s.mix : undefined;
  const pal = (r.wild ? PALETTES[r.wild.palette] : PALETTES.magma).map(hex);
  return {
    res: [width, height],
    seed: (r.seed % 1000) + 1,
    mixR: mix ? mix[0] : [1, 0, 0],
    mixG: mix ? mix[1] : [0, 1, 0],
    mixB: mix ? mix[2] : [0, 0, 1],
    mono: 'mono' in s && s.mono ? 1 : 0,
    contrast: s.contrast,
    gamma: s.gamma,
    sat: s.sat,
    lift: s.lift + r.fade,
    shadowTint: s.shadow,
    highTint: s.high,
    lutMix: r.lutMix,
    exposure: r.exposure,
    temp: r.temp,
    tint: r.tint,
    wType: r.wild ? WILDS[r.wild.type].id : 0,
    wAmt: r.wild?.amt ?? 0,
    wP: r.wild ? [r.wild.cx, r.wild.cy, r.wild.n, r.seed % 2] : [0.5, 0.5, 6, 0],
    pal0: pal[0],
    pal1: pal[1],
    pal2: pal[2],
    pal3: pal[3],
    pal4: pal[4],
    vignette: r.vignette,
    soft: r.soft,
    fringe: r.fringe,
    dbl: r.double?.amt ?? 0,
    dblT: r.double ? [r.double.dx, r.double.dy, r.double.rot, r.double.scale] : [0, 0, 0, 1],
    grain: r.grain,
    halation: r.halation,
    leak: r.leak?.amt ?? 0,
    leakPos: r.leak ? [r.leak.x, r.leak.y] : [0, 0],
    leakCol: r.leak ? hex(r.leak.color) : [0, 0, 0],
    dust: r.dust,
  };
}
