import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';
import { C } from '../theme';

export function Button({ title, onPress, kind = 'primary', disabled, busy }: {
  title: string; onPress: () => void; kind?: 'primary' | 'ghost'; disabled?: boolean; busy?: boolean;
}) {
  const off = disabled || busy;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={off}
      style={[s.btn, kind === 'ghost' ? s.ghost : s.primary, off && { opacity: 0.5 }]}
    >
      {busy ? <ActivityIndicator color={kind === 'ghost' ? C.accent : '#fff'} /> :
        <Text style={[s.btnText, kind === 'ghost' && { color: C.accent }]}>{title}</Text>}
    </Pressable>
  );
}

export function Field(props: TextInputProps & { label: string }) {
  const { label, ...rest } = props;
  return (
    <View style={{ gap: 4 }}>
      <Text style={s.label}>{label}</Text>
      <TextInput placeholderTextColor={C.muted} style={s.input} {...rest} />
    </View>
  );
}

export function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected: on }}
      style={[s.chip, on && s.chipOn]}>
      <Text style={[s.chipText, on && { color: '#fff' }]}>{label}</Text>
    </Pressable>
  );
}

export function Card({ children, tone }: { children: React.ReactNode; tone?: 'warn' | 'bad' | 'ok' }) {
  const bg = tone === 'warn' ? C.warnSoft : tone === 'bad' ? C.badSoft : tone === 'ok' ? C.okSoft : C.surface;
  return <View style={[s.card, { backgroundColor: bg }]}>{children}</View>;
}

export function ErrorText({ children }: { children?: string | null }) {
  return children ? <Text style={s.error}>{children}</Text> : null;
}

export function Bar({ label, value, max, unit, limit }: {
  label: string; value: number; max: number; unit: string; limit?: boolean;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const over = max > 0 && value > max;
  return (
    <View style={{ gap: 4 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <Text style={s.barLabel}>{label}</Text>
        <Text style={s.barLabel}>{Math.round(value)} / {Math.round(max)} {unit}{limit ? ' max' : ''}</Text>
      </View>
      <View style={s.track}><View style={[s.fill, { width: `${pct}%`, backgroundColor: over && limit ? C.bad : C.accent }]} /></View>
    </View>
  );
}

export const s = StyleSheet.create({
  btn: { minHeight: 46, borderRadius: 10, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  primary: { backgroundColor: C.accent },
  ghost: { borderWidth: 1, borderColor: C.accent, backgroundColor: 'transparent' },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  label: { color: C.muted, fontSize: 12, fontWeight: '600' },
  input: { borderWidth: 1, borderColor: C.line, backgroundColor: C.surface, borderRadius: 10, paddingHorizontal: 12, minHeight: 44, color: C.fg, fontSize: 15 },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.surface, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8 },
  chipOn: { backgroundColor: C.accent, borderColor: C.accent },
  chipText: { color: C.fg, fontSize: 13 },
  card: { borderWidth: 1, borderColor: C.line, borderRadius: 12, padding: 14, gap: 8 },
  error: { color: C.bad, fontSize: 13 },
  barLabel: { color: C.fg, fontSize: 13 },
  track: { height: 8, borderRadius: 4, backgroundColor: C.accentSoft, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4 },
  h1: { fontSize: 24, fontWeight: '700', color: C.fg },
  h2: { fontSize: 16, fontWeight: '700', color: C.fg },
  muted: { color: C.muted, fontSize: 13 },
  body: { color: C.fg, fontSize: 14, lineHeight: 20 },
});
