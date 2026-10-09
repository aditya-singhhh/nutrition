import * as Haptics from 'expo-haptics';
import React, { useEffect, useRef, useState } from 'react';
import { Animated, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path } from 'react-native-svg';
import { Press } from '../anim';
import { C } from '../theme';
import { K } from './ui';

export type Tab = 'home' | 'scan' | 'ask' | 'profile';
const TABS: { key: Tab; label: string }[] = [
  { key: 'home', label: 'Home' }, { key: 'scan', label: 'Scan' }, { key: 'ask', label: 'Ask' }, { key: 'profile', label: 'Profile' },
];

function Icon({ k, color }: { k: Tab; color: string }) {
  const p = { stroke: color, strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24">
      {k === 'home' && <Path {...p} d="M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10" />}
      {k === 'scan' && <Path {...p} d="M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3M7 12h10" />}
      {k === 'ask' && <Path {...p} d="M4 5h16v11H9l-5 4z" />}
      {k === 'profile' && <><Circle {...p} cx={12} cy={8} r={4} /><Path {...p} d="M4 21c1-4 4-6 8-6s7 2 8 6" /></>}
    </Svg>
  );
}

/** Bottom navigation. Its bottom padding equals the Android system-bar inset, so it never sits under back/home buttons. */
export default function TabBar({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  const { bottom } = useSafeAreaInsets();
  const [w, setW] = useState(0);
  const idx = TABS.findIndex((t) => t.key === tab);
  const x = useRef(new Animated.Value(idx)).current;
  useEffect(() => { Animated.spring(x, { toValue: idx, damping: 16, stiffness: 200, mass: 0.7, useNativeDriver: true }).start(); }, [idx, x]);
  const cell = w / TABS.length;
  return (
    <View style={{ backgroundColor: C.surface, borderTopWidth: 1, borderColor: C.line, paddingBottom: Math.max(bottom, 12), paddingTop: 10, elevation: 8 }}>
      <View onLayout={(e) => setW(e.nativeEvent.layout.width)} style={{ flexDirection: 'row', height: 60 }} accessibilityRole="tablist">
        {cell > 0 && <Animated.View style={{ position: 'absolute', top: 2, left: (cell - 64) / 2, width: 64, height: 32, borderRadius: 16, backgroundColor: C.pill,
          transform: [{ translateX: x.interpolate({ inputRange: TABS.map((_, i) => i), outputRange: TABS.map((_, i) => i * cell) }) }] }} />}
        {TABS.map((t) => {
          const on = t.key === tab;
          return (
            <Press key={t.key} accessibilityRole="tab" accessibilityLabel={t.label} accessibilityState={{ selected: on }}
              onPress={() => { Haptics.selectionAsync().catch(() => {}); onChange(t.key); }} style={{ width: cell || undefined, flex: cell ? undefined : 1, height: 60, alignItems: 'center' }}>
              <View style={{ height: 36, justifyContent: 'center' }}><Icon k={t.key} color={on ? C.ink : C.muted} /></View>
              <K color={on ? C.ink : C.muted} size={10}>{t.label}</K>
            </Press>
          );
        })}
      </View>
    </View>
  );
}
