import { useEffect, useRef, useState } from 'react';
import { BackHandler, Image, Pressable, Text, View, type ImageSourcePropType } from 'react-native';
import * as Haptics from 'expo-haptics';
import * as Sharing from 'expo-sharing';
import { File, Paths } from 'expo-file-system';
import { ImageFormat, makeImageFromView, type SkImage } from '@shopify/react-native-skia';
import { LOOKS, type Look } from './looks';
import { PrintFrame } from './PrintFrame';
import type { Stage } from './stage';
import { IMAGES, img } from './images';


const LABEL = 'BricolageGrotesque_800ExtraBold';

type Props = {
  stage: Stage;
  photo: SkImage;
  look: Look;
  onLook: (look: Look) => void;
  onBack: () => void;
};

// design/Print.dc.html: the print on a wall, with AGAIN, BACK and SHARE.
export function PrintScreen({ stage, photo, look, onLook, onBack }: Props) {
  const { u, left, top } = stage;
  const frame = useRef<View>(null);
  const [sharing, setSharing] = useState(false);

  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      onBack();
      return true;
    });
    return () => sub.remove();
  }, [onBack]);

  const again = () => {
    Haptics.selectionAsync();
    const rest = LOOKS.filter((x) => x !== look);
    onLook(rest[Math.floor(Math.random() * rest.length)]);
  };

  const back = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onBack();
  };

  // Snapshots the print as it looks on screen and hands it to the share sheet.
  const share = async () => {
    if (sharing) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setSharing(true);
    try {
      const image = await makeImageFromView(frame);
      if (!image) return;
      const file = new File(Paths.cache, `nopointcam-${Date.now()}.png`);
      file.write(image.encodeToBytes(ImageFormat.PNG));
      await Sharing.shareAsync(file.uri, { mimeType: 'image/png', UTI: 'public.png', dialogTitle: 'Share your print' });
    } catch {
      // Closing the share sheet or a failed snapshot leaves the print as it is.
    } finally {
      setSharing(false);
    }
  };

  const k = 1.06; // the design zooms the frame to 106%

  return (
    <View style={{ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, backgroundColor: '#1F1C2B', overflow: 'hidden' }}>
      {/* The wall, tiled at 512px like the design */}
      <View style={{ position: 'absolute', left, top, width: u(390), height: u(844) }}>
        {[0, 1].map((row) => (
          <Image key={row} fadeDuration={0} source={img(IMAGES.wall)} style={{ position: 'absolute', left: 0, top: u(512 * row), width: u(512), height: u(512) }} />
        ))}
      </View>

      <View style={{ position: 'absolute', left, top, width: u(390), height: u(844), paddingTop: u(64), paddingHorizontal: u(20), paddingBottom: u(30) }}>
        <View style={{ flexGrow: 1 }} />
        <View ref={frame} collapsable={false} style={{ alignSelf: 'center' }}>
          <PrintFrame photo={photo} look={look} k={u(k)} />
        </View>
        <View style={{ flexGrow: 1 }} />

        <View style={{ alignSelf: 'center', width: u(340), height: u(128) }}>
          <LabelledKey u={u} x={4} y={22} size={96} image={img(IMAGES.buttonPill)} text="AGAIN" labelGap={-10} a11y="Roll a new look" onPress={again} />
          <LabelledKey u={u} x={172} y={34} size={78} image={img(IMAGES.buttonAB)} text="BACK" a11y="B: back to camera" onPress={back} />
          <LabelledKey u={u} x={254} y={4} size={78} image={img(IMAGES.buttonAB)} text="SHARE" accent a11y="A: share" disabled={sharing} onPress={share} />
        </View>
      </View>
    </View>
  );
}

type KeyProps = {
  u: (n: number) => number;
  x: number;
  y: number;
  size: number;
  image: ImageSourcePropType;
  text: string;
  a11y: string;
  labelGap?: number;
  accent?: boolean;
  disabled?: boolean;
  onPress: () => void;
};

function LabelledKey({ u, x, y, size, image, text, a11y, labelGap = 2, accent, disabled, onPress }: KeyProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={a11y}
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      onPress={onPress}
      style={{ position: 'absolute', left: u(x), top: u(y), alignItems: 'center' }}
    >
      {({ pressed }) => (
        <>
          <Image fadeDuration={0} source={image} style={{ width: u(size), height: u(size), transform: pressed ? [{ translateY: u(3) }, { scale: 0.96 }] : [] }} />
          <Text
            style={{
              marginTop: u(labelGap),
              fontFamily: LABEL,
              fontStyle: 'italic',
              fontSize: u(10),
              letterSpacing: u(1.6),
              color: accent ? '#B8F23A' : '#9FA3AE',
            }}
          >
            {text}
          </Text>
        </>
      )}
    </Pressable>
  );
}
