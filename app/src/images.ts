import { Asset } from 'expo-asset';
import type { ImageSourcePropType } from 'react-native';

// Every image the screens use. They're all loaded before the camera appears (the splash
// screen stays up until then), so the board and buttons show up together instead of
// popping in one by one.
export const IMAGES = {
  board: require('../assets/np/board.jpg'),
  dpad: require('../assets/np/dpad.png'),
  buttonAB: require('../assets/np/button-ab.png'),
  buttonPill: require('../assets/np/button-select-start.png'),
  fan: require('../assets/np/fan-blades.png'),
  paper: require('../assets/np/paper-texture.jpg'),
  wall: require('../assets/np/wall-texture.jpg'),
} as const;

const local = new Map<number, string>();

export async function preloadImages() {
  const mods = Object.values(IMAGES) as number[];
  const assets = await Asset.loadAsync(mods);
  assets.forEach((a, i) => {
    if (a.localUri) local.set(mods[i], a.localUri);
  });
}

// The on-device copy once preloaded, otherwise the bundled module.
export function img(mod: number): ImageSourcePropType {
  const uri = local.get(mod);
  return uri ? { uri } : mod;
}
