import { StatusBar } from 'expo-status-bar';
import { Linking, Pressable, Text, View } from 'react-native';
import { useCameraPermissions } from 'expo-camera';
import { useFonts } from 'expo-font';
import { Silkscreen_400Regular } from '@expo-google-fonts/silkscreen';
import { BagelFatOne_400Regular } from '@expo-google-fonts/bagel-fat-one';
import { BricolageGrotesque_800ExtraBold } from '@expo-google-fonts/bricolage-grotesque';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { CameraScreen } from './src/CameraScreen';

export default function App() {
  const [fontsLoaded] = useFonts({ Silkscreen_400Regular, BagelFatOne_400Regular, BricolageGrotesque_800ExtraBold });
  const [permission, requestPermission] = useCameraPermissions();

  let screen = null;
  if (fontsLoaded && permission) {
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
