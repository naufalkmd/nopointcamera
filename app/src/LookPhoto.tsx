import {
  Blur,
  Canvas,
  Circle,
  ColorMatrix,
  Group,
  Image,
  RadialGradient,
  Rect,
  useImage,
  vec,
} from '@shopify/react-native-skia';
import { RECIPES, colorMatrix, type Look } from './looks';

const GRAIN = require('../assets/np/grain.png');

// Bokeh circles from design/Photo.dc.html, in its 268x335 space.
const BOKEH = [
  { x: 40, y: 60, r: 20, a: 0.45, c: '#FFE3B8' },
  { x: 214, y: 48, r: 28, a: 0.4, c: '#FFE9C9' },
  { x: 238, y: 206, r: 15, a: 0.45, c: '#FFD9A8' },
  { x: 66, y: 250, r: 24, a: 0.35, c: '#FFE3B8' },
  { x: 156, y: 82, r: 11, a: 0.55, c: '#FFF1D6' },
  { x: 196, y: 290, r: 17, a: 0.4, c: '#FFE3B8' },
  { x: 30, y: 312, r: 12, a: 0.45, c: '#FFF1D6' },
];

type Props = { uri: string; look: Look; width: number; height: number };

export function LookPhoto({ uri, look, width: w, height: h }: Props) {
  const photo = useImage(uri);
  const grain = useImage(GRAIN);
  const r = RECIPES[look];
  const k = w / 268; // design px -> this size
  const matrix = colorMatrix(look);
  const diag = Math.hypot(w, h);

  return (
    <Canvas style={{ width: w, height: h, backgroundColor: '#1A1712' }}>
      {photo && (
        <Group>
          <Image image={photo} x={0} y={0} width={w} height={h} fit="cover">
            <ColorMatrix matrix={matrix} />
            {r.blur ? <Blur blur={r.blur * k} mode="clamp" /> : null}
          </Image>
          {r.ghost ? (
            <Group
              opacity={r.ghost}
              blendMode="screen"
              origin={vec(w / 2, h / 2)}
              transform={[{ translateX: 34 * k }, { translateY: -12 * k }, { rotate: (9 * Math.PI) / 180 }, { scale: 1.15 }]}
            >
              <Image image={photo} x={0} y={0} width={w} height={h} fit="cover">
                <ColorMatrix matrix={matrix} />
              </Image>
            </Group>
          ) : null}
        </Group>
      )}
      {r.duo ? (
        <>
          <Rect x={0} y={0} width={w} height={h} color="#1D3FBB" blendMode="lighten" opacity={r.duo} />
          <Rect x={0} y={0} width={w} height={h} color="#FF5CAD" blendMode="darken" opacity={r.duo} />
        </>
      ) : null}
      {r.bokeh ? (
        <Group blendMode="screen" opacity={r.bokeh}>
          <Blur blur={1.5 * k} mode="decal" />
          {BOKEH.map((b, i) => (
            <Circle key={i} cx={b.x * k} cy={b.y * k} r={b.r * k} color={b.c} opacity={b.a} />
          ))}
        </Group>
      ) : null}
      {r.leak ? (
        <Group blendMode="screen" opacity={r.leak}>
          <Rect x={0} y={0} width={w} height={h}>
            <RadialGradient c={vec(w, 0)} r={diag} colors={['rgba(255,110,40,0.9)', 'rgba(255,110,40,0)']} positions={[0, 0.55]} />
          </Rect>
          <Rect x={0} y={0} width={w} height={h}>
            <RadialGradient c={vec(0, h)} r={diag} colors={['rgba(255,50,90,0.55)', 'rgba(255,50,90,0)']} positions={[0, 0.45]} />
          </Rect>
        </Group>
      ) : null}
      {r.vignette ? (
        <Rect x={0} y={0} width={w} height={h} opacity={r.vignette}>
          <RadialGradient c={vec(w / 2, h / 2)} r={diag / 2} colors={['rgba(20,14,8,0)', 'rgba(20,14,8,0.85)']} positions={[0.5, 1]} />
        </Rect>
      ) : null}
      {r.grain && grain ? (
        <Image image={grain} x={0} y={0} width={w} height={h} fit="cover" blendMode="overlay" opacity={r.grain} />
      ) : null}
    </Canvas>
  );
}
