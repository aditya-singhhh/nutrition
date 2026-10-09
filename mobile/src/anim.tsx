import React, { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Pressable, PressableProps, StyleProp, Text, TextStyle, ViewStyle } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

let reduce = false;
AccessibilityInfo.isReduceMotionEnabled().then((v) => { reduce = v; }).catch(() => {});
AccessibilityInfo.addEventListener('reduceMotionChanged', (v) => { reduce = v; });
export const dur = (ms: number) => (reduce ? 0 : ms);

/** Fade + rise on mount. Use `delay` to stagger a list of cards. */
export function FadeIn({ children, delay = 0, y = 14, style }: {
  children: React.ReactNode; delay?: number; y?: number; style?: StyleProp<ViewStyle>;
}) {
  const v = useRef(new Animated.Value(reduce ? 1 : 0)).current;
  useEffect(() => {
    Animated.timing(v, { toValue: 1, duration: dur(420), delay: reduce ? 0 : delay, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
  }, [v, delay]);
  return (
    <Animated.View style={[style, { opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [y, 0] }) }] }]}>
      {children}
    </Animated.View>
  );
}

/** Slides up from the bottom with a spring (bottom sheets). */
export function SheetIn({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const v = useRef(new Animated.Value(reduce ? 1 : 0)).current;
  useEffect(() => {
    if (reduce) return;
    Animated.spring(v, { toValue: 1, damping: 18, stiffness: 140, mass: 0.9, useNativeDriver: true }).start();
  }, [v]);
  return (
    <Animated.View style={[style, { opacity: v.interpolate({ inputRange: [0, 0.4, 1], outputRange: [0, 1, 1] }),
      transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [80, 0] }) }] }]}>
      {children}
    </Animated.View>
  );
}

/** Pressable that shrinks slightly while held. */
export function Press({ children, style, onPress, ...rest }: PressableProps & { style?: StyleProp<ViewStyle>; children: React.ReactNode }) {
  const v = useRef(new Animated.Value(1)).current;
  const to = (x: number) => Animated.spring(v, { toValue: x, damping: 15, stiffness: 320, mass: 0.6, useNativeDriver: true }).start();
  return (
    <Pressable {...rest} onPress={onPress} onPressIn={() => !reduce && to(0.96)} onPressOut={() => to(1)}>
      <Animated.View style={[style, { transform: [{ scale: v }] }]}>{children}</Animated.View>
    </Pressable>
  );
}

/** Number that counts up to its value. */
export function CountUp({ value, style, fmt = (n: number) => String(Math.round(n)) }: {
  value: number; style?: StyleProp<TextStyle>; fmt?: (n: number) => string;
}) {
  const v = useRef(new Animated.Value(0)).current;
  const [txt, setTxt] = useState(fmt(reduce ? value : 0));
  useEffect(() => {
    const id = v.addListener(({ value: x }) => setTxt(fmt(x)));
    Animated.timing(v, { toValue: value, duration: dur(900), easing: Easing.out(Easing.cubic), useNativeDriver: false }).start(() => setTxt(fmt(value)));
    return () => v.removeListener(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return <Text style={style}>{txt}</Text>;
}

/** Horizontal bar whose fill animates to `pct` (0-100). */
export function FillBar({ pct, color, track, height = 8 }: { pct: number; color: string; track: string; height?: number }) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(v, { toValue: Math.max(0, Math.min(100, pct)), duration: dur(800), delay: reduce ? 0 : 150, easing: Easing.out(Easing.cubic), useNativeDriver: false }).start();
  }, [v, pct]);
  return (
    <Animated.View style={{ height, borderRadius: height / 2, backgroundColor: track, overflow: 'hidden' }}>
      <Animated.View style={{ height, borderRadius: height / 2, backgroundColor: color, width: v.interpolate({ inputRange: [0, 100], outputRange: ['0%', '100%'] }) }} />
    </Animated.View>
  );
}

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
/** Circular score ring that sweeps to value/100. */
export function Ring({ value, size = 120, stroke = 12, color, track, children }: {
  value: number; size?: number; stroke?: number; color: string; track: string; children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(v, { toValue: Math.max(0, Math.min(100, value)), duration: dur(1000), delay: reduce ? 0 : 200, easing: Easing.out(Easing.cubic), useNativeDriver: false }).start();
  }, [v, value]);
  return (
    <Animated.View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={{ position: 'absolute' }}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={track} strokeWidth={stroke} fill="none" />
        <AnimatedCircle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={`${c} ${c}`} strokeDashoffset={v.interpolate({ inputRange: [0, 100], outputRange: [c, 0] })}
          transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </Svg>
      {children}
    </Animated.View>
  );
}

/** Looping vertical sweep for the scan laser. */
export function Laser({ height, color }: { height: number; color: string }) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (reduce) { v.setValue(0.5); return; }
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(v, { toValue: 1, duration: 1500, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      Animated.timing(v, { toValue: 0, duration: 1500, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [v]);
  return (
    <Animated.View style={{ position: 'absolute', left: 14, right: 14, top: 0, height: 2, backgroundColor: color,
      shadowColor: color, shadowOpacity: 0.8, shadowRadius: 8, elevation: 4,
      transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [12, height - 14] }) }] }} />
  );
}

/** Gently pulsing wrapper (corner brackets). */
export function Pulse({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (reduce) return;
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(v, { toValue: 1, duration: 900, useNativeDriver: true }),
      Animated.timing(v, { toValue: 0, duration: 900, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [v]);
  return <Animated.View style={[style, { opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.7, 1] }), transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.985, 1.015] }) }] }]}>{children}</Animated.View>;
}
