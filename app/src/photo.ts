import { FilterMode, MipmapMode, Skia, type SkImage } from '@shopify/react-native-skia';

// The biggest place a shot is shown (the Print screen) needs about 900x1100 px,
// so every shot is decoded once and shrunk to this, then shared by all the screens.
const SHOT_MAX = 1200;

export async function loadShot(uri: string): Promise<SkImage | null> {
  const data = await Skia.Data.fromURI(uri);
  const full = Skia.Image.MakeImageFromEncoded(data);
  if (!full) return null;
  const fw = full.width();
  const fh = full.height();
  const k = SHOT_MAX / Math.max(fw, fh);
  if (k >= 1) return full;
  const w = Math.round(fw * k);
  const h = Math.round(fh * k);
  const surface = Skia.Surface.Make(w, h);
  if (!surface) return full;
  surface
    .getCanvas()
    .drawImageRectOptions(full, Skia.XYWHRect(0, 0, fw, fh), Skia.XYWHRect(0, 0, w, h), FilterMode.Linear, MipmapMode.Linear);
  surface.flush();
  const small = surface.makeImageSnapshot();
  full.dispose();
  return small;
}

// Picks the smallest 4:3 capture size that's still sharp enough, so the camera doesn't
// shoot and process a full-resolution photo only for it to be shrunk. iOS only lists
// widescreen or tiny sizes, which would narrow the view, so iOS keeps its default.
export function pickPictureSize(sizes: string[]): string | undefined {
  const fits = sizes
    .map((size) => {
      const m = /^(\d+)x(\d+)$/.exec(size);
      if (!m) return null;
      const long = Math.max(+m[1], +m[2]);
      const short = Math.min(+m[1], +m[2]);
      return { size, long, short };
    })
    .filter((x): x is { size: string; long: number; short: number } => !!x && Math.abs(x.long / x.short - 4 / 3) < 0.02 && x.short >= 1080)
    .sort((a, b) => a.long * a.short - b.long * b.short);
  return fits[0]?.size;
}
