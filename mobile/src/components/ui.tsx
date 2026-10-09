import * as Haptics from 'expo-haptics';
import React, { useRef, useState } from 'react';
import { ActivityIndicator, Animated, StyleSheet, Text, TextInput, TextInputProps, View, ViewStyle, StyleProp } from 'react-native';
import { FillBar, Press, dur } from '../anim';
import { C, F } from '../theme';

const tap = () => { Haptics.selectionAsync().catch(() => {}); };

/** Small tracked-out UPPERCASE label. */
export function K({ children, color = C.muted, size = 11, style }: { children: React.ReactNode; color?: string; size?: number; style?: any }) {
  return <Text style={[{ fontFamily: F.label, fontSize: size, letterSpacing: size * 0.13, textTransform: 'uppercase', color }, style]}>{children}</Text>;
}
/** Big condensed UPPERCASE heading. */
export function Display({ children, size = 34, color = C.fg, style }: { children: React.ReactNode; size?: number; color?: string; style?: any }) {
  return <Text style={[{ fontFamily: F.display, fontSize: size, lineHeight: size * 1.02, textTransform: 'uppercase', letterSpacing: size * 0.01, color }, style]}>{children}</Text>;
}

export function Button({ title, onPress, kind = 'primary', disabled, busy, style }: {
  title: string; onPress: () => void; kind?: 'primary' | 'tonal' | 'dark'; disabled?: boolean; busy?: boolean; style?: StyleProp<ViewStyle>;
}) {
  const off = disabled || busy;
  const bg = kind === 'primary' ? C.accent : kind === 'dark' ? C.ink : C.track;
  const fg = kind === 'tonal' ? C.fg : '#fff';
  return (
    <Press accessibilityRole="button" accessibilityLabel={title} disabled={off} onPress={() => { tap(); onPress(); }}
      style={[{ height: 54, borderRadius: 27, backgroundColor: bg, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 20, opacity: off ? 0.45 : 1 }, style]}>
      {busy ? <ActivityIndicator color={fg} /> : <K color={fg} size={13}>{title}</K>}
    </Press>
  );
}

/** Outlined field with the label sitting on the border. */
export function Field({ label, bg = C.bg, mono, ...rest }: TextInputProps & { label: string; bg?: string; mono?: boolean }) {
  const [focus, setFocus] = useState(false);
  return (
    <View style={{ minHeight: 56 }}>
      <View style={[s.field, { borderColor: focus ? C.accent : '#6D7D73', borderWidth: focus ? 2 : 1.5 }]}>
        <TextInput {...rest} onFocus={(e) => { setFocus(true); rest.onFocus?.(e); }} onBlur={(e) => { setFocus(false); rest.onBlur?.(e); }}
          placeholderTextColor="#7A8A80" accessibilityLabel={label}
          style={{ flex: 1, fontFamily: mono ? F.mono : F.body, fontSize: mono ? 18 : 17, color: C.fg, paddingVertical: 0 }} />
      </View>
      <View style={{ position: 'absolute', left: 12, top: -8, backgroundColor: bg, paddingHorizontal: 4 }}><K size={10}>{label}</K></View>
    </View>
  );
}

export function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Press accessibilityRole="button" accessibilityState={{ selected: on }} onPress={() => { tap(); onPress(); }}
      style={{ minHeight: 40, paddingHorizontal: 14, borderRadius: 12, justifyContent: 'center', backgroundColor: on ? C.ink : C.surface, borderWidth: 1, borderColor: on ? C.ink : C.line }}>
      <K color={on ? '#fff' : C.fg} size={11}>{label}</K>
    </Press>
  );
}

/** Segmented control with a gliding thumb. */
export function Segmented({ options, value, onChange, dark }: {
  options: { key: string; label: string }[]; value: string; onChange: (k: string) => void; dark?: boolean;
}) {
  const [w, setW] = useState(0);
  const idx = Math.max(0, options.findIndex((o) => o.key === value));
  const x = useRef(new Animated.Value(idx)).current;
  React.useEffect(() => { Animated.spring(x, { toValue: idx, damping: 18, stiffness: 220, mass: 0.7, useNativeDriver: true }).start(); }, [idx, x]);
  const cell = w > 0 ? (w - 8) / options.length : 0;
  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)} accessibilityRole="tablist"
      style={{ height: 48, borderRadius: 24, padding: 4, flexDirection: 'row', backgroundColor: dark ? 'rgba(10,18,14,.6)' : C.track,
        borderWidth: dark ? 1 : 0, borderColor: 'rgba(255,255,255,.14)' }}>
      {cell > 0 && <Animated.View style={{ position: 'absolute', left: 4, top: 4, bottom: 4, width: cell, borderRadius: 20,
        backgroundColor: dark ? '#fff' : C.ink, transform: [{ translateX: x.interpolate({ inputRange: options.map((_, i) => i), outputRange: options.map((_, i) => i * cell) }) }] }} />}
      {options.map((o) => (
        <Press key={o.key} accessibilityRole="tab" accessibilityState={{ selected: o.key === value }} onPress={() => { tap(); onChange(o.key); }}
          style={{ width: cell || undefined, flex: cell ? undefined : 1, height: 40, alignItems: 'center', justifyContent: 'center' }}>
          <K size={10} color={o.key === value ? (dark ? C.ink : '#fff') : dark ? '#D5DED3' : C.fg} style={{ letterSpacing: 1 }}>{o.label}</K>
        </Press>
      ))}
    </View>
  );
}

export function Card({ children, tone, style }: { children: React.ReactNode; tone?: 'warn' | 'bad' | 'ok' | 'ink'; style?: StyleProp<ViewStyle> }) {
  const bg = tone === 'warn' ? C.warnSoft : tone === 'bad' ? C.badSoft : tone === 'ok' ? C.okSoft : tone === 'ink' ? C.ink : C.surface;
  return <View style={[{ backgroundColor: bg, borderRadius: 20, padding: 16, gap: 10 }, style]}>{children}</View>;
}

export function Tag({ label, tone = 'ok' }: { label: string; tone?: 'ok' | 'warn' | 'bad' }) {
  const [bg, fg] = tone === 'ok' ? [C.accentSoft, C.accentText] : tone === 'warn' ? [C.warnSoft, C.warn] : [C.badSoft, C.bad];
  return <View style={{ backgroundColor: bg, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, alignSelf: 'flex-start' }}><K color={fg} size={10}>{label}</K></View>;
}

export function ErrorText({ children }: { children?: string | null }) {
  return children ? <Text style={{ color: C.bad, fontFamily: F.bodyMed, fontSize: 14 }} accessibilityLiveRegion="polite">{children}</Text> : null;
}

export function Bar({ label, value, max, unit, limit }: { label: string; value: number; max: number; unit: string; limit?: boolean }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const over = max > 0 && value > max;
  return (
    <View style={{ gap: 6 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <K color={C.fg}>{label}</K>
        <Text style={[s.num, { color: C.muted }]}>{Math.round(value)} / {Math.round(max)} {unit}{limit ? ' max' : ''}</Text>
      </View>
      <FillBar pct={pct} color={over && limit ? C.bad : C.accent} track={C.track} />
    </View>
  );
}

export const s = StyleSheet.create({
  field: { height: 56, borderRadius: 12, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center' },
  num: { fontFamily: F.bodyMed, fontSize: 13, fontVariant: ['tabular-nums'] },
  body: { fontFamily: F.body, fontSize: 15, lineHeight: 21, color: C.fg },
  muted: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.muted },
  strong: { fontFamily: F.bodyBold, fontSize: 16, color: C.fg },
});
void dur;
