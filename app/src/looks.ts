// The 8 looks from design/Photo.dc.html. The design fakes them with CSS filters;
// here each CSS filter chain is turned into the same colour matrix (Filter Effects spec)
// so the phone matches the canvas. Later this becomes the shader pipeline in FILTERS.md.

export const LOOKS = ['expired', 'infrared', 'riso', 'double', 'bluehour', 'dreamy', 'noir', 'pastel'] as const;
export type Look = (typeof LOOKS)[number];

export const LOOK_NAMES: Record<Look, string> = {
  expired: 'EXPIRED',
  infrared: 'INFRARED',
  riso: 'RISO',
  double: 'DOUBLE',
  bluehour: 'BLUE HOUR',
  dreamy: 'DREAMY',
  noir: 'NOIR',
  pastel: 'PASTEL',
};

type Step =
  | ['sepia' | 'saturate' | 'contrast' | 'brightness' | 'grayscale', number]
  | ['hue', number]; // degrees

export type LookRecipe = {
  steps: Step[];
  blur?: number; // px at the design's 268px width
  ghost?: number; // double exposure strength
  duo?: number; // riso two-ink overlay
  bokeh?: number;
  leak?: number;
  vignette?: number;
  grain?: number;
};

export const RECIPES: Record<Look, LookRecipe> = {
  expired: { steps: [['sepia', 0.45], ['saturate', 1.1], ['contrast', 0.9], ['brightness', 1.08], ['hue', -10]], leak: 0.85, vignette: 0.5, grain: 0.5 },
  infrared: { steps: [['hue', 180], ['saturate', 1.45], ['contrast', 1.1], ['brightness', 1.04]], vignette: 0.35, grain: 0.4 },
  riso: { steps: [['grayscale', 1], ['contrast', 1.35], ['brightness', 1.05]], duo: 1, grain: 0.7 },
  double: { steps: [['saturate', 0.9], ['contrast', 1.05]], ghost: 0.55, vignette: 0.45, grain: 0.45 },
  bluehour: { steps: [['sepia', 0.3], ['hue', 180], ['saturate', 1.5], ['brightness', 0.85], ['contrast', 1.15]], vignette: 0.65, grain: 0.5 },
  dreamy: { steps: [['saturate', 1.2], ['brightness', 1.08]], blur: 2, bokeh: 1, vignette: 0.25, grain: 0.3 },
  noir: { steps: [['grayscale', 1], ['contrast', 1.4], ['brightness', 0.92]], vignette: 0.7, grain: 0.8 },
  pastel: { steps: [['saturate', 0.7], ['brightness', 1.12], ['contrast', 0.85], ['hue', -15]], leak: 0.3, grain: 0.3 },
};

// An RGB affine transform: 3x3 linear part plus an offset, offsets in 0..1.
type Affine = { m: number[]; o: [number, number, number] };

function stepAffine([kind, v]: Step): Affine {
  const lin = (m: number[]): Affine => ({ m, o: [0, 0, 0] });
  switch (kind) {
    case 'grayscale': {
      const s = 1 - v;
      return lin([
        0.2126 + 0.7874 * s, 0.7152 - 0.7152 * s, 0.0722 - 0.0722 * s,
        0.2126 - 0.2126 * s, 0.7152 + 0.2848 * s, 0.0722 - 0.0722 * s,
        0.2126 - 0.2126 * s, 0.7152 - 0.7152 * s, 0.0722 + 0.9278 * s,
      ]);
    }
    case 'sepia': {
      const s = 1 - v;
      return lin([
        0.393 + 0.607 * s, 0.769 - 0.769 * s, 0.189 - 0.189 * s,
        0.349 - 0.349 * s, 0.686 + 0.314 * s, 0.168 - 0.168 * s,
        0.272 - 0.272 * s, 0.534 - 0.534 * s, 0.131 + 0.869 * s,
      ]);
    }
    case 'saturate':
      return lin([
        0.213 + 0.787 * v, 0.715 - 0.715 * v, 0.072 - 0.072 * v,
        0.213 - 0.213 * v, 0.715 + 0.285 * v, 0.072 - 0.072 * v,
        0.213 - 0.213 * v, 0.715 - 0.715 * v, 0.072 + 0.928 * v,
      ]);
    case 'hue': {
      const r = (v * Math.PI) / 180;
      const c = Math.cos(r);
      const s = Math.sin(r);
      return lin([
        0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928,
        0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.14, 0.072 - c * 0.072 - s * 0.283,
        0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072,
      ]);
    }
    case 'brightness':
      return lin([v, 0, 0, 0, v, 0, 0, 0, v]);
    case 'contrast': {
      const t = 0.5 - 0.5 * v;
      return { m: [v, 0, 0, 0, v, 0, 0, 0, v], o: [t, t, t] };
    }
  }
}

// b applied after a.
function then(a: Affine, b: Affine): Affine {
  const m: number[] = [];
  const o: [number, number, number] = [0, 0, 0];
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      m[r * 3 + c] = b.m[r * 3] * a.m[c] + b.m[r * 3 + 1] * a.m[3 + c] + b.m[r * 3 + 2] * a.m[6 + c];
    }
    o[r] = b.m[r * 3] * a.o[0] + b.m[r * 3 + 1] * a.o[1] + b.m[r * 3 + 2] * a.o[2] + b.o[r];
  }
  return { m, o };
}

// A 4x5 matrix for Skia's ColorMatrix (row-major, alpha untouched).
export function colorMatrix(look: Look): number[] {
  const id: Affine = { m: [1, 0, 0, 0, 1, 0, 0, 0, 1], o: [0, 0, 0] };
  const { m, o } = RECIPES[look].steps.map(stepAffine).reduce(then, id);
  return [
    m[0], m[1], m[2], 0, o[0],
    m[3], m[4], m[5], 0, o[1],
    m[6], m[7], m[8], 0, o[2],
    0, 0, 0, 1, 0,
  ];
}

// Picks a new look and the reel of looks the readout flicks through before landing on it.
export function rollLook(last: Look): { fx: Look; reel: Look[] } {
  const pick = (pool: Look[]) => pool[Math.floor(Math.random() * pool.length)];
  const fx = pick(LOOKS.filter((x) => x !== last));
  const reel: Look[] = [];
  for (let i = 0; i < 6; i++) {
    const prev = reel[i - 1] ?? last;
    reel.push(pick(LOOKS.filter((x) => x !== prev && x !== fx)));
  }
  reel.push(fx);
  return { fx, reel };
}

// Gaps between reel ticks, slowing down like a slot machine (ms).
export const REEL_DELAYS = [0, 45, 55, 70, 90, 120, 160];
