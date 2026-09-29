// A look is a recipe (FILTERS.md section 2): a small object built from a seed, so the
// viewfinder, the print and the share image all render the same thing, and the same
// seed always rebuilds the same look. AGAIN just picks a new seed.

export type Tier = 'common' | 'rare' | 'legendary';

type RGB = [number, number, number];

// Film looks (FILTERS.md stage 1), written as parametric grades rather than LUT files.
// Named by feel, not after real film brands.
export type Stock = {
  name: string;
  contrast: number; // blend towards an S-curve; negative flattens
  gamma: number;
  sat: number;
  lift: number; // faded blacks
  shadow: RGB; // added to the shadows
  high: RGB; // multiplied into the highlights
  mono?: boolean;
  mix?: [RGB, RGB, RGB]; // channel mixer rows, for false-colour stocks
  halation?: [number, number]; // forced halation range
};

export const STOCKS = {
  warm400: { name: 'WARM 400', contrast: 0.1, gamma: 0.95, sat: 0.95, lift: 0.03, shadow: [0.01, 0.005, -0.01], high: [1.04, 1.0, 0.93] },
  vivid100: { name: 'VIVID 100', contrast: 0.35, gamma: 1.0, sat: 1.35, lift: 0, shadow: [-0.01, 0, 0.02], high: [1.03, 1.0, 0.96] },
  slide50: { name: 'SLIDE 50', contrast: 0.55, gamma: 1.08, sat: 1.55, lift: 0, shadow: [0.01, -0.015, 0.02], high: [1.02, 0.99, 1.0] },
  green400: { name: 'GREEN 400', contrast: 0.2, gamma: 0.98, sat: 1.1, lift: 0.02, shadow: [-0.015, 0.015, 0], high: [1.0, 1.02, 0.97] },
  golden: { name: 'GOLDEN', contrast: 0.25, gamma: 0.95, sat: 1.15, lift: 0.02, shadow: [0.015, 0.008, -0.015], high: [1.06, 1.02, 0.88] },
  tungsten: { name: 'TUNGSTEN', contrast: 0.3, gamma: 1.0, sat: 1.1, lift: 0.02, shadow: [-0.02, 0.01, 0.04], high: [1.08, 0.98, 0.9], halation: [0.6, 0.9] },
  instant: { name: 'INSTANT', contrast: -0.15, gamma: 0.9, sat: 0.85, lift: 0.1, shadow: [-0.02, 0.02, 0.035], high: [1.05, 1.0, 0.9] },
  expired: { name: 'EXPIRED', contrast: -0.1, gamma: 0.92, sat: 0.9, lift: 0.08, shadow: [0.03, -0.01, 0.03], high: [1.08, 0.97, 0.85] },
  push1600: { name: 'PUSH 1600', contrast: 0.6, gamma: 1.05, sat: 1, lift: 0, shadow: [0, 0, 0], high: [1, 1, 1], mono: true },
  softbw: { name: 'SOFT B&W', contrast: 0.2, gamma: 0.95, sat: 1, lift: 0.04, shadow: [0.01, 0.005, 0], high: [1.02, 1.0, 0.97], mono: true },
  bleach: { name: 'BLEACH', contrast: 0.6, gamma: 1.05, sat: 0.45, lift: 0, shadow: [0, 0, 0.01], high: [1.0, 1.0, 1.02] },
  bluehour: { name: 'BLUE HOUR', contrast: 0.35, gamma: 1.1, sat: 1.2, lift: 0.02, shadow: [-0.03, 0, 0.06], high: [0.9, 0.98, 1.1] },
  pastel: { name: 'PASTEL', contrast: -0.25, gamma: 0.85, sat: 0.7, lift: 0.1, shadow: [0.02, 0, 0.03], high: [1.05, 1.02, 1.0] },
  infrared: {
    name: 'INFRARED',
    contrast: 0.25,
    gamma: 1.0,
    sat: 1.3,
    lift: 0,
    shadow: [0, 0, 0.02],
    high: [1, 0.95, 1],
    mix: [[0.1, 1.0, -0.1], [0.9, 0.1, 0], [0, 0.1, 0.9]],
  },
} satisfies Record<string, Stock>;
export type StockId = keyof typeof STOCKS;

// Wild effects for the rare and legendary tiers (FILTERS.md section 3). The number is the
// effect's id in the shader.
export const WILDS = {
  gameboy: { id: 1, name: 'GAME BOY', pixel: true },
  thermal: { id: 2, name: 'THERMAL', pixel: false },
  poster: { id: 3, name: 'POSTER', pixel: true },
  halftone: { id: 4, name: 'HALFTONE', pixel: true },
  riso: { id: 5, name: 'RISO', pixel: true },
  glitch: { id: 6, name: 'GLITCH', pixel: false },
  kaleido: { id: 7, name: 'KALEIDO', pixel: false },
  swirl: { id: 8, name: 'SWIRL', pixel: false },
  melt: { id: 9, name: 'MELT', pixel: false },
  solarize: { id: 10, name: 'SOLARIZE', pixel: false },
} as const;
export type WildId = keyof typeof WILDS;

// Curated palettes, dark to light (FILTERS.md: never fully random RGB).
export const PALETTES: Record<string, string[]> = {
  magma: ['#000004', '#3B0F70', '#8C2981', '#FE9F6D', '#FCFDBF'],
  sunset: ['#1A0633', '#6A0D83', '#CE4993', '#EE5D6C', '#FB9062'],
  acid: ['#0B0033', '#3D1E6D', '#B8F23A', '#F7FF58', '#FFFFFF'],
  vapor: ['#1B1035', '#FF71CE', '#01CDFE', '#05FFA1', '#FFFB96'],
  ocean: ['#03045E', '#0077B6', '#00B4D8', '#90E0EF', '#CAF0F8'],
  candy: ['#2B0F54', '#AB1F65', '#FF4F5A', '#FF9E2C', '#FFF56D'],
  toxic: ['#0D1B2A', '#1B998B', '#2DE1C2', '#C5F76A', '#F8FFE5'],
  risoClassic: ['#1D1D1B', '#FF48B0', '#0078BF', '#FFE800', '#F2ECE0'],
  ember: ['#120C0C', '#6E0B0B', '#D62828', '#F77F00', '#FCBF49'],
  mint: ['#1E0F0A', '#4A2C2A', '#3FB28F', '#A8E6CF', '#F5FFF9'],
  ultra: ['#10002B', '#5A189A', '#9D4EDD', '#E0AAFF', '#FDF0FF'],
  duo: ['#0A0A23', '#E0115F', '#00B3B3', '#F5E663', '#FAFAFA'],
};

const RISO_PALETTES = ['risoClassic', 'vapor', 'duo', 'candy', 'ocean'];

export type Recipe = {
  seed: number;
  tier: Tier;
  stock: StockId;
  lutMix: number;
  exposure: number;
  temp: number;
  tint: number;
  fade: number;
  wild: { type: WildId; amt: number; palette: string; cx: number; cy: number; n: number } | null;
  vignette: number;
  soft: number;
  fringe: number;
  double: { amt: number; dx: number; dy: number; rot: number; scale: number } | null;
  grain: number;
  halation: number;
  leak: { amt: number; x: number; y: number; color: string } | null;
  dust: number;
  tilt: number;
};

const LEAK_COLORS = ['#FF6E28', '#FF325A', '#FFB347', '#FF4FA0'];

// mulberry32: a tiny seeded random number generator.
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function newSeed() {
  return Math.floor(Math.random() * 2 ** 31);
}

export function makeRecipe(seed: number, forceTier?: Tier): Recipe {
  const r = rng(seed);
  const range = (a: number, b: number) => a + (b - a) * r();
  const chance = (p: number) => r() < p;
  const pick = <T,>(xs: readonly T[]) => xs[Math.floor(r() * xs.length)];

  const roll = r();
  const tier: Tier = forceTier ?? (roll < 0.03 ? 'legendary' : roll < 0.15 ? 'rare' : 'common');
  const stock = pick(Object.keys(STOCKS) as StockId[]);
  const s: Stock = STOCKS[stock];

  let wild: Recipe['wild'] = null;
  if (tier !== 'common') {
    const legendary = tier === 'legendary';
    const type = pick(Object.keys(WILDS) as WildId[]);
    wild = {
      type,
      amt: legendary ? range(1.6, 2) : range(0.6, 1),
      // Riso prints with two bright inks, so it only uses ink-friendly palettes.
      palette: pick(type === 'riso' ? RISO_PALETTES : Object.keys(PALETTES)),
      cx: range(0.3, 0.7),
      cy: range(0.3, 0.7),
      n: legendary ? pick([10, 12]) : pick([6, 8]),
    };
  }
  // Pixel effects (Game Boy, halftone, riso, poster) replace the image's texture, so the
  // film effects that would muddy them are left out.
  const pixel = !!wild && WILDS[wild.type].pixel;

  const double: Recipe['double'] =
    !pixel && tier === 'common' && chance(0.12)
      ? { amt: range(0.4, 0.6), dx: range(-0.12, 0.12), dy: range(-0.08, 0.08), rot: range(-12, 12), scale: range(1.05, 1.2) }
      : null;
  // No light leak together with a double exposure.
  const leak: Recipe['leak'] =
    !pixel && !double && chance(0.35)
      ? { amt: range(0.4, 0.9), x: pick([0, 1]) + range(-0.1, 0.1), y: range(0, 1), color: pick(LEAK_COLORS) }
      : null;
  // Strong grain only on black-and-white stocks.
  const grain = pixel ? range(0, 0.1) : s.mono ? range(0.35, 0.8) : chance(0.25) ? 0 : range(0.08, 0.35);
  const halation = pixel ? 0 : s.halation ? range(s.halation[0], s.halation[1]) : chance(0.4) ? range(0.1, 0.35) : 0;

  return {
    seed,
    tier,
    stock,
    lutMix: range(0.6, 1),
    exposure: range(-0.25, 0.25),
    temp: range(-0.5, 0.5),
    tint: range(-0.3, 0.3),
    fade: range(0, 0.04),
    wild,
    vignette: pixel ? range(0, 0.3) : range(0.1, 0.6),
    soft: !pixel && chance(0.12) ? range(0.3, 0.7) : 0,
    fringe: !pixel && chance(0.3) ? range(0.5, 1.5) : 0,
    double,
    grain,
    halation,
    leak,
    dust: !pixel && chance(0.3) ? range(0.3, 1) : 0,
    tilt: tier === 'common' ? range(-2, 2) : range(-3, 3),
  };
}

export function recipeName(recipe: Recipe) {
  return recipe.wild ? WILDS[recipe.wild.type].name : STOCKS[recipe.stock].name;
}

// Every name the readout can land on, for the rolling reel.
export const ALL_NAMES = [...Object.values(STOCKS).map((s) => s.name), ...Object.values(WILDS).map((w) => w.name)];

export const TIER_COLORS: Record<Tier, string> = {
  common: '#D8FF6A',
  rare: '#7FE3FF',
  legendary: '#FFD84A',
};
