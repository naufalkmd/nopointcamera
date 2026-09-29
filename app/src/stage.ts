import { useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export type Stage = { s: number; u: (n: number) => number; left: number; top: number; cutout: boolean };

// Screens are laid out in the design's 390x844 space and scaled to fill the phone's width,
// edge to edge. Only board art sits below y=800, so on short phones the bottom is cropped
// rather than shrinking everything; if even that doesn't fit, the stage shrinks to height.
export function useStage(): Stage {
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const s = Math.min(width / 390, height / 800);
  return {
    s,
    u: (n: number) => n * s,
    left: (width - 390 * s) / 2,
    top: Math.max(0, (height - 844 * s) / 2),
    // A notch or Dynamic Island sits in the middle of the bezel's top edge.
    cutout: insets.top > 24,
  };
}
