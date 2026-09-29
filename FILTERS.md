# nopointcam: filter and style design

Every press takes the same kind of photo, then runs it through a random "camera setting". This doc covers how to build that system so it can go from tasteful film looks to completely unhinged, while still usually looking good.

## 1. Pipeline

Every photo goes through the same stages, in this order:

```
camera frame
 → 1. colour grade    a LUT picked from a curated set, at 60–100% strength
 → 2. tone            exposure, contrast, colour temperature/tint, faded blacks
 → 3. wild effect     at most one: geometry, colour, pixel, depth/segmentation or time (see section 3)
 → 4. optics          vignette, soft blur/bokeh, slight colour fringing, double exposure
 → 5. film texture    grain, halation (red glow around highlights), light leak, dust
 → 6. framing         crop, slight rotation, the print frame
```

Build it as GPU shaders: Metal or Core Image on iOS, OpenGL/Vulkan on Android, WebGL on the web, Skia or fragment shaders in React Native or Flutter. The current design prototype fakes the looks with CSS filters; that's fine for a mock-up, not for the app.

## 2. A look is a recipe

Each shot stores a small recipe, so the print, the share image and the saved photo all match:

```json
{
  "seed": 91822,
  "tier": "rare",
  "lut": "portra-ish",
  "lutMix": 0.8,
  "exposure": 0.15,
  "temp": 12,
  "wild": { "type": "thermal", "palette": "sunset-neon" },
  "grain": 0.35,
  "halation": 0.4,
  "leak": { "tex": "leak-03", "x": 0.9, "y": 0.1 },
  "vignette": 0.5,
  "tilt": -1.5
}
```

Rules that keep randomness from looking broken:

- **Curated base, random extras.** Pick 1 of 12–20 LUTs you like, then randomize the rest.
- **A safe range for every value, plus some rules.** For example, strong grain only on monochrome looks, or no light leak together with a double exposure.
- **Save the seed with the photo.** The same seed rebuilds the same look. AGAIN just picks a new seed.
- **Same pipeline for preview and capture.** Run it at low resolution on the live preview and full resolution on capture, so what you see is what prints.

## 3. Crazy effects

### Break the geometry
- **Pixel sorting:** bright pixels melt into streaks.
- **Slit-scan:** each row comes from a slightly different moment, so anything moving stretches and warps.
- **Kaleidoscope and mirror folds.**
- **Fisheye, or a swirl** around a random point.
- **Displacement:** warp the photo through a noise pattern, glass ripples or a random texture.

### Break the colour
- **Fake thermal / false colour:** map brightness onto a wild gradient (black → purple → orange → yellow).
- **Posterize to 3–4 colours** with a random neon palette.
- **Channel swaps and solarize.**
- **Riso misregistration:** two ink layers printed slightly off from each other.

### Break the pixels
- **Game Boy Camera look:** 4 shades of green with a dither pattern. This matches the console and should be a signature look.
- **Halftone dots, ASCII characters, 1-bit dithering, mosaic tiles.**
- **Glitch:** red/green/blue channels pulled apart, sliced scanlines shifted sideways, datamosh-style smearing.

### Use what the camera knows
- **Depth** (the iPhone depth map, or on-device depth estimation):
  - fog that builds with distance;
  - the background gets a different effect than the subject;
  - fake tilt-shift miniature.
- **Person segmentation** (Apple Vision, MediaPipe):
  - the subject stays normal while the world goes thermal;
  - a neon outline around people;
  - the background replaced with a pattern.
- **Face mesh** (MediaPipe): warp faces, add extra eyes, turn faces into a mosaic.

### Use time
- **Echo:** blend the last few frames together, so movement leaves trails.
- **Colour delay:** the red, green and blue channels come from different frames.

## 4. Crazy without ugly

- **Rarity tiers.** Most shots are nice film looks, about 1 in 8 is weird, and about 1 in 40 is completely unhinged. Rare shots feel like a lucky pull, which fits "no point". You could show the tier subtly on the print, like a foil corner.

  | Tier | Odds | What it gets |
  |---|---|---|
  | common | ~85% | LUT + tone + optics + film texture |
  | rare | ~12% | the above + one wild effect from section 3 |
  | legendary | ~3% | an extreme wild effect or an AI transform (section 5) |

- **One wild effect per shot**, on top of a good colour grade, never three stacked.
- **Curated palettes.** Neon gradients and posterize colours come from 10–15 picked palettes, never fully random RGB.
- **Protect the subject.** With segmentation, the wild effect hits the background harder than faces, so the photo still reads.

## 5. Libraries and sources

### Pipelines by platform

| Platform | Pipeline | Ready-made looks |
|---|---|---|
| iOS | Core Image (`CIColorCube` applies LUTs), Metal, GPUImage3 | Built-in `CIPhotoEffect*` looks (Chrome, Fade, Instant, Noir, Process, Transfer) |
| Android | CameraX + OpenGL/Vulkan shaders, android-gpuimage | GPUImage filters |
| React Native | react-native-vision-camera + react-native-skia shaders on live frames | Write your own |
| Web | WebGL: pixi-filters, glfx.js, pmndrs/postprocessing | pixi-filters (old film, colour split, glitch, dot, ASCII, twist, bulge, shockwave); CSSgram (Instagram-style CSS) |
| Flutter | Fragment shaders | Write your own |

### Colour presets (LUTs)
- **RawTherapee Film Simulation** pack: free, hundreds of film stocks (Portra, Ektar, Velvia, Tri-X, Polaroid and more), as HaldCLUT images.
- **G'MIC** film emulations.
- Paid, higher-end: **Dehancer**, **FilmConvert**.

LUTs come as `.cube` or HaldCLUT files and can be applied with one small shader on any platform.

### Crazy effects
- **Hydra** (hydra-synth): a web video synth that takes camera input and chains feedback, kaleidoscope, modulate and colour ops in one line of code. The fastest way to discover wild combos before porting them to shaders.
- **ISF shaders** (Interactive Shader Format): a large free library of portable GLSL video effects (glitch, slit-scan, kaleidoscope, halftone and more).
- **Shadertoy:** references for pixel sorting, datamosh, dithering, halation, bloom, VHS/CRT.
- **MediaPipe / Apple Vision:** segmentation and face tracking for the "subject vs world" effects.
- **AI image-to-image** (Replicate: Flux Kontext, SDXL + ControlNet): turns a scene into clay, a painting or another world. Slow and costs money per shot, so keep it for the legendary tier.

### Textures
Light leaks, dust and grain: free packs exist, or generate them in code (the paper and grain in `assets/` were made by `scripts/make_textures.py`).

Check the licence on any LUT, shader or texture pack before shipping it in a commercial app.

## 6. Recommended starting set

1. 12–20 film LUTs from the free RawTherapee pack.
2. 4–5 base shaders: grain, halation, vignette, light leak, double exposure.
3. 6–8 wild shaders for the rare tier: Game Boy dither, thermal, pixel sort, slit-scan, halftone, riso, glitch, kaleidoscope.
4. The seeded recipe generator with rarity tiers and curated palettes.
5. Later: segmentation-based effects, then AI transforms for the legendary tier.

## 7. What the app has so far

Built in `app/src/film/`, running on captured photos in Expo Go:

- **Recipe generator** (`recipe.ts`): seeded, with the rarity tiers (85% / 12% / 3%), 12 curated palettes and the rules above (strong grain only on black and white, no light leak with a double exposure, pixel effects skip the film texture). AGAIN picks a new seed.
- **14 film looks** written as parametric grades instead of LUT files, named by feel rather than after film brands: WARM 400, VIVID 100, SLIDE 50, GREEN 400, GOLDEN, TUNGSTEN, INSTANT, EXPIRED, PUSH 1600, SOFT B&W, BLEACH, BLUE HOUR, PASTEL, INFRARED. Real `.cube` or HaldCLUT files can replace the grade step later (check their licence first).
- **One shader** (`develop.ts`) for the whole pipeline: grade and tone, one wild effect, vignette, softness, colour fringing, double exposure, grain, halation, light leak and dust.
- **10 wild effects:** Game Boy dither, thermal, posterize, halftone, riso, glitch, kaleidoscope, swirl, melt (pixel sort) and solarize. Legendary shots get extreme versions.
- **Tier on the print:** the readout lands in the tier's colour, rare and legendary shots get stronger haptics, and their prints have a silver or gold foil corner. Prints on the Print screen sit at the recipe's slight tilt.

Not yet: the live preview is unfiltered (it needs VisionCamera and a development build), and slit-scan, echo and colour delay need several frames. Depth, segmentation, face mesh and AI transforms are later steps.

