import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  AccessibilityInfo,
  Animated,
  Easing,
  Image,
  Pressable,
  Text,
  View,
  type ImageSourcePropType,
} from 'react-native';
import { CameraView, type CameraType } from 'expo-camera';
import * as Haptics from 'expo-haptics';
import { Canvas, Oval, RadialGradient, vec, type SkImage } from '@shopify/react-native-skia';
import { TIER_COLORS, makeRecipe, newSeed, recipeName, type Recipe, type Tier } from './film/recipe';
import { LookPhoto } from './LookPhoto';
import { PrintFrame } from './PrintFrame';
import { PrintScreen } from './PrintScreen';
import { loadShot, pickPictureSize } from './photo';
import { IMAGES, img } from './images';
import { useStage } from './stage';

const PIXEL = 'Silkscreen_400Regular';

// Gaps between reel ticks, slowing down like a slot machine (ms).
const REEL_DELAYS = [0, 45, 55, 70, 90, 120, 160];

// The reel teases looks on the way to the real one, leaning on the rare ones for fun.
function teaser(): Recipe {
  const roll = Math.random();
  const tier: Tier = roll < 0.5 ? 'common' : roll < 0.9 ? 'rare' : 'legendary';
  return makeRecipe(newSeed(), tier);
}

// Development only: the D-pad cycles a forced tier, so the rare looks can be checked
// without shooting forty times.
const FORCE_CYCLE: (Tier | undefined)[] = [undefined, 'rare', 'legendary', 'common'];
const FORCE_LABELS = ['RANDOM', 'ALL RARE', 'ALL LEGEND', 'ALL COMMON'];

function useLoop(ms: number, easing = Easing.linear) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const anim = Animated.loop(Animated.timing(v, { toValue: 1, duration: ms, easing, useNativeDriver: true }));
    anim.start();
    return () => anim.stop();
  }, [v, ms, easing]);
  return v;
}

type Print = { photo: SkImage; recipe: Recipe; n: number };

// A rare pull should feel like one: stronger haptics as the tier goes up.
function landHaptics(tier: Tier) {
  if (tier === 'common') {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    return;
  }
  const hits = tier === 'rare' ? 2 : 4;
  for (let i = 0; i < hits; i++) setTimeout(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy), i * 110);
}

export function CameraScreen() {
  const stage = useStage();
  const { s, u, left, top, cutout } = stage;
  const cam = useRef<CameraView>(null);
  const [ready, setReady] = useState(false);
  const [facing, setFacing] = useState<CameraType>('back');
  const [flashOn, setFlashOn] = useState(true);
  const [review, setReview] = useState<Recipe | null>(null);
  const [rolling, setRolling] = useState(false);
  const [shot, setShot] = useState<SkImage | null>(null);
  const [pictureSize, setPictureSize] = useState<string | undefined>();
  const sizeChecked = useRef(false);
  const [print, setPrint] = useState<Print | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [printing, setPrinting] = useState(false);

  const force = useRef(0);
  const busy = useRef(false);
  const shots = useRef(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const flash = useRef(new Animated.Value(0)).current;

  const later = (fn: () => void, ms: number) => {
    timers.current.push(setTimeout(fn, ms));
  };
  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };
  useEffect(() => clearTimers, []);

  const say = (text: string) => {
    setMessage(text);
    later(() => setMessage(null), 1200);
  };

  const shoot = async () => {
    if (busy.current || !ready || !cam.current) return;
    busy.current = true;
    clearTimers();
    setMessage(null);
    const recipe = makeRecipe(newSeed(), FORCE_CYCLE[force.current]);
    const reel = [...Array.from({ length: REEL_DELAYS.length - 1 }, teaser), recipe];
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    if (flashOn) {
      flash.setValue(1);
      Animated.timing(flash, { toValue: 0, duration: 500, delay: 70, useNativeDriver: true }).start();
    }
    setShot(null);
    setRolling(true);
    setReview(reel[0]);

    // The readout rolls while the photo is taken and decoded, which also hides the delay.
    // The shot is decoded once, shrunk, and shared by the viewfinder, the slot and Print.
    const capture = cam.current
      .takePictureAsync({ quality: 0.85 })
      .then((p) => loadShot(p.uri))
      .then((img) => {
        if (img) setShot(img);
        return img;
      })
      .catch(() => null);
    let t = 0;
    reel.forEach((r, i) => {
      t += REEL_DELAYS[i];
      if (i > 0)
        later(() => {
          setReview(r);
          Haptics.selectionAsync();
        }, t);
    });
    await new Promise((r) => setTimeout(r, t));
    const photo = await capture;

    setRolling(false);
    busy.current = false;
    if (!photo) {
      setReview(null);
      say('NO FILM');
      return;
    }
    shots.current += 1;
    setPrint({ photo, recipe, n: shots.current });
    landHaptics(recipe.tier);
    const name = recipeName(recipe).toLowerCase();
    AccessibilityInfo.announceForAccessibility(recipe.tier === 'common' ? `Look: ${name}` : `${recipe.tier} look: ${name}`);
    later(() => setReview(null), recipe.tier === 'common' ? 1600 : 2400);
  };

  const flip = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setFacing((f) => (f === 'back' ? 'front' : 'back'));
  };
  const toggleFlash = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setFlashOn((f) => !f);
  };
  const openPrint = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (!print) {
      say('NO PRINTS');
      return;
    }
    clearTimers();
    setReview(null);
    setPrinting(true);
  };
  const dpad = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (!__DEV__) return;
    force.current = (force.current + 1) % FORCE_CYCLE.length;
    say(FORCE_LABELS[force.current]);
  };

  const settled = !!review && !rolling;
  const readout = message ?? (review ? recipeName(review) : 'READY');
  const landedColor = settled && review ? TIER_COLORS[review.tier] : '#D8FF6A';
  const readoutColor = message || settled ? landedColor : rolling ? '#7FA833' : '#3E5A1C';

  // Board animations, as in design/CameraBuilt.dc.html.
  const drift = useLoop(11000, Easing.inOut(Easing.ease));
  const fan = useLoop(350);
  const chase = useLoop(2200);
  const glow = useLoop(1600, Easing.inOut(Easing.ease));

  const box = (x: number, y: number, w: number, h: number) => ({ position: 'absolute' as const, left: u(x), top: u(y), width: u(w), height: u(h) });

  return (
    <View style={{ flex: 1, backgroundColor: '#050806' }}>
      <View style={{ position: 'absolute', left, top, width: u(390), height: u(844), overflow: 'hidden' }}>
        {/* The circuit board seen through the shell */}
        <Animated.View
          pointerEvents="none"
          style={[
            box(0, 0, 390, 844),
            {
              transform: [
                { translateX: drift.interpolate({ inputRange: [0, 0.33, 0.66, 1], outputRange: [0, u(1.5), u(-1.5), 0] }) },
                { translateY: drift.interpolate({ inputRange: [0, 0.33, 0.66, 1], outputRange: [0, u(-2), u(1), 0] }) },
              ],
            },
          ]}
        >
          <Image fadeDuration={0} source={img(IMAGES.board)} style={box(-10, -10, 410, 864)} />
          <View style={[box(58, 431, 276, 14), { overflow: 'hidden', mixBlendMode: 'screen' }]}>
            <Animated.View style={{ transform: [{ translateX: chase.interpolate({ inputRange: [0, 1], outputRange: [u(-40), u(290)] }) }] }}>
              <Canvas style={{ width: u(36), height: u(14) }}>
                <Oval x={0} y={0} width={u(36)} height={u(14)}>
                  <RadialGradient c={vec(u(18), u(7))} r={u(18)} colors={['rgba(255,255,255,1)', 'rgba(255,255,255,0)']} positions={[0, 0.62]} />
                </Oval>
              </Canvas>
            </Animated.View>
          </View>
          <Animated.Image
            fadeDuration={0}
            source={img(IMAGES.fan)}
            style={[box(168.4, 579.7, 43.5, 43.5), { transform: [{ rotate: fan.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }] }]}
          />
        </Animated.View>

        {/* The see-through shell */}
        <View pointerEvents="none" style={[box(0, 0, 390, 844), { backgroundColor: '#B8F23A', mixBlendMode: 'overlay', opacity: 0.4 }]} />
        <View
          pointerEvents="none"
          style={[
            box(0, 0, 390, 844),
            {
              borderRadius: u(52),
              boxShadow: `inset 0 0 0 ${u(2)}px #D8FF6A, inset 0 0 ${u(14)}px ${u(2)}px rgba(184, 242, 58, 0.7), inset 0 0 ${u(44)}px ${u(6)}px rgba(255, 60, 200, 0.28)`,
            },
          ]}
        />
        <View pointerEvents="none" style={[box(5, 84, 2, 300), { borderRadius: u(1), backgroundColor: 'rgba(255, 255, 255, 0.5)' }]} />
        <View pointerEvents="none" style={[box(6, 444, 2, 200), { borderRadius: u(1), backgroundColor: 'rgba(255, 255, 255, 0.35)' }]} />
        <View pointerEvents="none" style={[box(383, 452, 1.5, 180), { borderRadius: u(1), backgroundColor: 'rgba(255, 255, 255, 0.3)' }]} />

        {/* Bezel, flash LED and the look readout */}
        <View
          style={[
            box(16, 6, 358, 408),
            {
              backgroundColor: '#000000',
              borderTopLeftRadius: u(42),
              borderTopRightRadius: u(42),
              borderBottomRightRadius: u(72),
              borderBottomLeftRadius: u(18),
              borderWidth: u(1.5),
              borderColor: 'rgba(216, 255, 106, 0.35)',
            },
          ]}
        />
        <Animated.View
          pointerEvents="none"
          style={[
            box(34, 196, 8, 8),
            {
              borderRadius: u(4),
              backgroundColor: '#FF3B2F',
              boxShadow: `0 0 ${u(4)}px ${u(1)}px rgba(255, 59, 47, 0.9)`,
              opacity: flashOn ? glow.interpolate({ inputRange: [0, 0.5, 1], outputRange: [1, 0.55, 1] }) : 0.12,
            },
          ]}
        />
        <View
          importantForAccessibility="no-hide-descendants"
          accessibilityElementsHidden
          style={[
            // Beside the Dynamic Island or notch when there is one, centred as in the design otherwise.
            cutout ? box(262, 20, 96, 26) : box(125, 20, 140, 26),
            {
              borderRadius: u(6),
              backgroundColor: '#0A1406',
              boxShadow: `inset 0 ${u(1)}px ${u(3)}px rgba(0, 0, 0, 0.9)`,
              alignItems: 'center',
              justifyContent: 'center',
            },
          ]}
        >
          <Text
            style={{
              fontFamily: PIXEL,
              fontSize: u(cutout ? 10 : 12),
              letterSpacing: u(cutout ? 0.5 : 1),
              color: readoutColor,
              textShadowColor: settled || message ? landedColor : 'transparent',
              textShadowRadius: u(6),
            }}
          >
            {readout}
          </Text>
        </View>

        {/* Viewfinder: live camera, then the shot with its look while it's being revealed */}
        <View style={[box(63, 60, 264, 330), { borderRadius: u(4), overflow: 'hidden', backgroundColor: '#000000' }]}>
          <CameraView
            ref={cam}
            style={{ width: u(264), height: u(330) }}
            facing={facing}
            mirror={facing === 'front'}
            flash={flashOn ? (facing === 'front' ? 'screen' : 'on') : 'off'}
            animateShutter={false}
            active={!printing}
            pictureSize={pictureSize}
            onCameraReady={() => {
              setReady(true);
              if (sizeChecked.current) return;
              sizeChecked.current = true;
              cam.current
                ?.getAvailablePictureSizesAsync()
                .then((sizes) => setPictureSize(pickPictureSize(sizes)))
                .catch(() => {});
            }}
          />
          {review && shot ? (
            <View style={{ position: 'absolute', left: 0, top: 0 }}>
              <LookPhoto photo={shot} recipe={review} width={u(264)} height={u(330)} />
            </View>
          ) : null}
          <View
            pointerEvents="none"
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              width: u(264),
              height: u(330),
              boxShadow: `inset 0 0 0 ${u(1)}px rgba(0, 0, 0, 0.8), inset 0 ${u(2)}px ${u(6)}px rgba(0, 0, 0, 0.7)`,
            }}
          />
          <Animated.View pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, width: u(264), height: u(330), backgroundColor: '#FFFFFF', opacity: flash }} />
        </View>
        <View pointerEvents="none" style={[box(101, 401, 188, 5), { borderRadius: u(3), backgroundColor: '#0C0C0C', boxShadow: `inset 0 ${u(2)}px ${u(2)}px rgba(0, 0, 0, 0.9)` }]} />

        {/* Glowing A/B pill and the speaker */}
        <View
          pointerEvents="none"
          style={[
            box(212, 518, 154, 74),
            {
              borderRadius: u(37),
              backgroundColor: 'rgba(190, 255, 70, 0.22)',
              borderWidth: u(2),
              borderColor: 'rgba(225, 255, 140, 0.9)',
              boxShadow: `0 0 ${u(12)}px rgba(184, 242, 58, 0.6), inset 0 0 ${u(12)}px rgba(184, 242, 58, 0.35)`,
              transform: [{ rotate: '-35deg' }],
            },
          ]}
        />
        <Speaker u={u} />

        {/* Buttons and their markings */}
        <Key u={u} x={33} y={503} size={124} image={img(IMAGES.dpad)} label="D-pad, does nothing" onPress={dpad} />
        <Key u={u} x={221} y={543} size={70} image={img(IMAGES.buttonAB)} label="B: flip camera" onPress={flip} />
        <Key u={u} x={287} y={497} size={70} image={img(IMAGES.buttonAB)} label="A: take a photo" onPress={shoot} />
        <Key u={u} x={118} y={658} size={64} image={img(IMAGES.buttonPill)} label="Select: flash" selected={flashOn} onPress={toggleFlash} />
        <Key u={u} x={183} y={658} size={64} image={img(IMAGES.buttonPill)} label="Start: open the latest print" onPress={openPrint} />
        <Marking u={u} x={271} y={608} w={24} size={15}>B</Marking>
        <Marking u={u} x={337} y={562} w={24} size={15}>A</Marking>
        <Marking u={u} x={118} y={716} w={64} size={9}>SELECT</Marking>
        <Marking u={u} x={183} y={716} w={64} size={9}>START</Marking>

        {/* The print dropping out of the slot; tap it to open Print */}
        <View style={[box(109, 405, 172, 92), { overflow: 'hidden' }]}>
          {print ? (
            <View pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, width: u(172), height: u(92) }}>
              <SlotPrint key={print.n} print={print} s={s} />
            </View>
          ) : null}
          <View pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, width: u(172), height: u(10), experimental_backgroundImage: 'linear-gradient(180deg, rgba(0,0,0,0.6), rgba(0,0,0,0))' }} />
          {/* A clear tap area on top, so the Skia canvas in the print can't swallow the touch */}
          {print ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Open the latest print"
              onPress={openPrint}
              style={{ position: 'absolute', left: 0, top: 0, width: u(172), height: u(92), backgroundColor: 'rgba(0, 0, 0, 0.001)' }}
            />
          ) : null}
        </View>
      </View>

      {printing && print ? (
        <PrintScreen
          stage={stage}
          photo={print.photo}
          recipe={print.recipe}
          // AGAIN picks a new seed for the same photo (FILTERS.md section 2).
          onAgain={() => setPrint({ ...print, recipe: makeRecipe(newSeed(), FORCE_CYCLE[force.current]) })}
          onBack={() => setPrinting(false)}
        />
      ) : null}
    </View>
  );
}

function SlotPrint({ print, s }: { print: Print; s: number }) {
  const drop = useRef(new Animated.Value(-130 * s)).current;
  useEffect(() => {
    Animated.timing(drop, { toValue: 0, duration: 900, easing: Easing.bezier(0.2, 0.8, 0.2, 1), useNativeDriver: true }).start();
  }, [drop]);
  return (
    <Animated.View style={{ position: 'absolute', left: 0, top: -139.5 * s, transform: [{ translateY: drop }] }}>
      <PrintFrame photo={print.photo} recipe={print.recipe} k={0.5 * s} />
    </Animated.View>
  );
}

type KeyProps = {
  u: (n: number) => number;
  x: number;
  y: number;
  size: number;
  image: ImageSourcePropType;
  label: string;
  selected?: boolean;
  onPress: () => void;
};

function Key({ u, x, y, size, image, label, selected, onPress }: KeyProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={selected === undefined ? undefined : { selected }}
      onPress={onPress}
      style={{ position: 'absolute', left: u(x), top: u(y), width: u(size), height: u(size) }}
    >
      {({ pressed }) => (
        <Image
            fadeDuration={0}
          source={image}
          style={{
            width: u(size),
            height: u(size),
            opacity: pressed ? 0.8 : 1,
            transform: pressed ? [{ translateY: u(2) }, { scale: 0.95 }] : [],
          }}
        />
      )}
    </Pressable>
  );
}

function Marking({ u, x, y, w, size, children }: { u: (n: number) => number; x: number; y: number; w: number; size: number; children: ReactNode }) {
  return (
    <Text
      accessible={false}
      importantForAccessibility="no"
      pointerEvents="none"
      style={{
        position: 'absolute',
        left: u(x),
        top: u(y),
        width: u(w),
        textAlign: 'center',
        fontFamily: PIXEL,
        fontSize: u(size),
        letterSpacing: size < 12 ? u(0.5) : 0,
        color: '#F2F6E6',
        textShadowColor: 'rgba(0, 0, 0, 0.9)',
        textShadowOffset: { width: 0, height: u(1) },
        textShadowRadius: u(4),
      }}
    >
      {children}
    </Text>
  );
}

// The round speaker grille, bottom right.
function Speaker({ u }: { u: (n: number) => number }) {
  const bars = [
    { x: 21, y1: 34, y2: 68 },
    { x: 33, y1: 22, y2: 80 },
    { x: 45, y1: 16, y2: 86 },
    { x: 57, y1: 16, y2: 86 },
    { x: 69, y1: 22, y2: 80 },
    { x: 81, y1: 34, y2: 68 },
  ];
  return (
    <View
      pointerEvents="none"
      style={{
        position: 'absolute',
        left: u(252),
        top: u(688),
        width: u(108),
        height: u(108),
        borderRadius: u(54),
        borderWidth: u(3),
        borderColor: 'rgba(220, 255, 130, 0.9)',
        backgroundColor: 'rgba(8, 18, 10, 0.4)',
        boxShadow: `0 0 ${u(10)}px rgba(184, 242, 58, 0.5), inset 0 0 ${u(10)}px rgba(184, 242, 58, 0.3)`,
      }}
    >
      <View style={{ width: u(102), height: u(102), transform: [{ rotate: '-30deg' }] }}>
        {bars.map((b) => (
          <View
            key={b.x}
            style={{
              position: 'absolute',
              left: u(b.x - 3.5),
              top: u(b.y1 - 3.5),
              width: u(7),
              height: u(b.y2 - b.y1 + 7),
              borderRadius: u(3.5),
              backgroundColor: '#070A08',
            }}
          />
        ))}
      </View>
    </View>
  );
}
