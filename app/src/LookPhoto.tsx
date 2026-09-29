import { useMemo } from 'react';
import { Canvas, Fill, ImageShader, Shader, Skia, type SkImage } from '@shopify/react-native-skia';
import { DEVELOP_SKSL, developUniforms } from './film/develop';
import type { Recipe } from './film/recipe';

// Compiled once; every photo on every screen is drawn through it.
const DEVELOP = Skia.RuntimeEffect.Make(DEVELOP_SKSL);
if (!DEVELOP) console.error('nopointcam: the develop shader failed to compile');

type Props = { photo: SkImage; recipe: Recipe; width: number; height: number };

// A shot developed with its recipe (FILTERS.md pipeline), filling width x height.
export function LookPhoto({ photo, recipe, width: w, height: h }: Props) {
  const uniforms = useMemo(() => developUniforms(recipe, w, h), [recipe, w, h]);
  return (
    <Canvas style={{ width: w, height: h, backgroundColor: '#1A1712' }}>
      {DEVELOP ? (
        <Fill>
          <Shader source={DEVELOP} uniforms={uniforms}>
            {/* Mirrored edges, so bending effects like the swirl never show a gap */}
            <ImageShader image={photo} fit="cover" rect={{ x: 0, y: 0, width: w, height: h }} tx="mirror" ty="mirror" />
          </Shader>
        </Fill>
      ) : null}
    </Canvas>
  );
}
