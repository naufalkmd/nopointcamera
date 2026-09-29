import { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';
import { Linking, Pressable, Text, View } from 'react-native';
import { useCameraPermissions } from 'expo-camera';
import { useFonts } from 'expo-font';
import { Silkscreen_400Regular } from '@expo-google-fonts/silkscreen/400Regular';
import { BricolageGrotesque_800ExtraBold } from '@expo-google-fonts/bricolage-grotesque/800ExtraBold';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { CameraScreen } from './src/CameraScreen';
import { preloadImages } from './src/images';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function App() {
  const [fontsLoaded] = useFonts({
    Silkscreen_400Regular,
    BricolageGrotesque_800ExtraBold,
    // The logo font, trimmed to basic Latin (the full file is 1.5 MB). OFL, see assets/fonts.
    BagelFatOne_400Regular: require('./assets/fonts/BagelFatOne-Latin.ttf'),
  });
  const [permission, requestPermission] = useCameraPermissions();
  const [imagesLoaded, setImagesLoaded] = useState(false);

  useEffect(() => {
    preloadImages()
      .catch(() => {})
      .finally(() => setImagesLoaded(true));
  }, []);

  const ready = fontsLoaded && imagesLoaded && !!permission;
  useEffect(() => {
    if (ready) SplashScreen.hideAsync().catch(() => {});
  }, [ready]);

  let screen = null;
  if (ready && permission) {
    screen = permission.granted ? (
      <CameraScreen />
    ) : (
      <CameraAsk
        canAsk={permission.canAskAgain}
        onPress={() => (permission.canAskAgain ? requestPermission() : Linking.openSettings())}
      />
    );
  }

  return (
    <SafeAreaProvider>
      <StatusBar hidden />
      <View style={{ flex: 1, backgroundColor: '#050806' }}>{screen}</View>
    </SafeAreaProvider>
  );
}

// Placeholder until the design has a permission screen.
function CameraAsk({ canAsk, onPress }: { canAsk: boolean; onPress: () => void }) {
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 28, padding: 32 }}>
      <Text style={{ fontFamily: 'BagelFatOne_400Regular', fontSize: 40, color: '#D8FF6A' }}>nopointcam</Text>
      <Text style={{ fontFamily: 'Silkscreen_400Regular', fontSize: 13, lineHeight: 20, color: '#B8C79A', textAlign: 'center' }}>
        {canAsk ? 'IT NEEDS YOUR CAMERA TO TAKE PHOTOS' : 'CAMERA IS OFF. TURN IT ON IN SETTINGS'}
      </Text>
      <Pressable
        accessibilityRole="button"
        onPress={onPress}
        style={({ pressed }) => ({
          minHeight: 48,
          paddingHorizontal: 28,
          justifyContent: 'center',
          borderRadius: 24,
          borderWidth: 2,
          borderColor: '#D8FF6A',
          backgroundColor: pressed ? 'rgba(184, 242, 58, 0.3)' : 'rgba(184, 242, 58, 0.15)',
        })}
      >
        <Text style={{ fontFamily: 'Silkscreen_400Regular', fontSize: 14, color: '#D8FF6A' }}>{canAsk ? 'ALLOW CAMERA' : 'OPEN SETTINGS'}</Text>
      </Pressable>
    </View>
  );
}
