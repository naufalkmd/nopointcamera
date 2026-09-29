import { Image, Text, View } from 'react-native';
import type { SkImage } from '@shopify/react-native-skia';
import { LookPhoto } from './LookPhoto';
import type { Recipe, Tier } from './film/recipe';
import { IMAGES, img } from './images';

// Rare and legendary prints get a foil corner (FILTERS.md section 4): silver and gold.
const FOIL: Record<Exclude<Tier, 'common'>, [string, string]> = {
  rare: ['#B9C0CC', '#F1F4F8'],
  legendary: ['#C9982A', '#FFE59A'],
};

type Props = { photo: SkImage; recipe: Recipe; k: number; tilt?: boolean };

// design/Frame.dc.html: a 344x469 frame holding a 300x425 paper print. `k` scales it (0.5 in
// the slot). With `tilt`, the paper sits at the recipe's slight angle (the framing stage).
export function PrintFrame({ photo, recipe, k, tilt }: Props) {
  const u = (n: number) => n * k;
  const foil = recipe.tier === 'common' ? null : FOIL[recipe.tier];
  return (
    <View style={{ width: u(344), height: u(469) }}>
      <View
        style={{
          position: 'absolute',
          left: u(22),
          top: u(22),
          width: u(300),
          height: u(425),
          borderRadius: u(3),
          backgroundColor: '#EEE8DA',
          overflow: 'hidden',
          boxShadow: `0 ${u(12)}px ${u(16)}px rgba(0, 0, 0, 0.38), inset 0 0 ${u(28)}px rgba(125, 98, 52, 0.3)`,
          transform: tilt ? [{ rotate: `${recipe.tilt}deg` }] : [],
        }}
      >
        <View style={{ position: 'absolute', width: u(300), height: u(425), opacity: 0.9, mixBlendMode: 'soft-light' }}>
          <Image fadeDuration={0} source={img(IMAGES.paper)} style={{ width: u(300), height: u(425) }} />
        </View>
        <View style={{ position: 'absolute', left: u(16), top: u(16), width: u(268), height: u(335), borderRadius: u(2), overflow: 'hidden' }}>
          <LookPhoto photo={photo} recipe={recipe} width={u(268)} height={u(335)} />
        </View>
        <Text
          style={{
            position: 'absolute',
            left: 0,
            top: u(371),
            width: u(212),
            textAlign: 'right',
            fontFamily: 'BagelFatOne_400Regular',
            fontSize: u(22),
            lineHeight: u(26),
            color: '#2E2819',
            opacity: 0.9,
          }}
        >
          nopointcam
        </Text>
        {foil ? (
          <>
            <View
              style={{
                position: 'absolute',
                right: 0,
                bottom: 0,
                width: 0,
                height: 0,
                borderBottomWidth: u(40),
                borderLeftWidth: u(40),
                borderBottomColor: foil[0],
                borderLeftColor: 'transparent',
              }}
            />
            <View
              style={{
                position: 'absolute',
                right: 0,
                bottom: 0,
                width: 0,
                height: 0,
                borderBottomWidth: u(22),
                borderLeftWidth: u(22),
                borderBottomColor: foil[1],
                borderLeftColor: 'transparent',
                opacity: 0.8,
              }}
            />
          </>
        ) : null}
      </View>
    </View>
  );
}
