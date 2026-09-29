import { Image, Text, View } from 'react-native';
import { LookPhoto } from './LookPhoto';
import type { Look } from './looks';

const PAPER = require('../assets/np/paper-texture.png');

// design/Frame.dc.html: a 344x469 frame holding a 300x425 paper print. `k` scales it (0.5 in the slot).
export function PrintFrame({ uri, look, k }: { uri: string; look: Look; k: number }) {
  const u = (n: number) => n * k;
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
        }}
      >
        <View style={{ position: 'absolute', width: u(300), height: u(425), opacity: 0.9, mixBlendMode: 'soft-light' }}>
          <Image source={PAPER} style={{ width: u(300), height: u(425) }} />
        </View>
        <View style={{ position: 'absolute', left: u(16), top: u(16), width: u(268), height: u(335), borderRadius: u(2), overflow: 'hidden' }}>
          <LookPhoto uri={uri} look={look} width={u(268)} height={u(335)} />
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
      </View>
    </View>
  );
}
