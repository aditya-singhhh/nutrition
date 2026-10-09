import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Switch, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle } from 'react-native-svg';
import { FadeIn, SheetIn } from '../anim';
import { api, getBaseUrl, setBaseUrl, setToken } from '../api';
import { Button, Display, ErrorText, Field, K, LangToggle, Segmented, s } from '../components/ui';
import { useT } from '../i18n';
import { C, F } from '../theme';

export default function AuthScreen({ onDone }: { onDone: () => void }) {
  const { t: tr } = useT();
  const { top, bottom } = useSafeAreaInsets();
  const [server, setServer] = useState(getBaseUrl());
  const [editServer, setEditServer] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [consent, setConsent] = useState(false);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true); setErr(null);
    try {
      await setBaseUrl(server);
      const res = mode === 'login' ? await api.login(email.trim(), password) : await api.register(email.trim(), password);
      await setToken(res.access_token);
      onDone();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <KeyboardAvoidingView behavior="padding" style={{ flex: 1, backgroundColor: C.ink }}>
      <View style={{ position: 'absolute', right: 16, top: top + 8, zIndex: 2 }}><LangToggle /></View>
      <View style={{ paddingTop: top + 56, paddingHorizontal: 24, gap: 18 }}>
        <FadeIn>
          <Svg width={64} height={64} viewBox="0 0 64 64">
            <Circle cx={32} cy={32} r={26} stroke="#2B3B33" strokeWidth={8} fill="none" />
            <Circle cx={32} cy={32} r={26} stroke={C.gold} strokeWidth={8} fill="none" strokeLinecap="round" strokeDasharray="114 163" transform="rotate(-90 32 32)" />
          </Svg>
        </FadeIn>
        <FadeIn delay={100}><Display size={56} color="#fff">Health{'\n'}Companion</Display></FadeIn>
        <FadeIn delay={200}><K color={C.onInk} size={12}>{tr('tagline')}</K></FadeIn>
      </View>
      <View style={{ flex: 1 }} />
      <SheetIn style={{ backgroundColor: C.bg, borderTopLeftRadius: 28, borderTopRightRadius: 28, maxHeight: '72%' }}>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingBottom: Math.max(bottom, 12) + 20, gap: 20 }}>
          <Segmented options={[{ key: 'login', label: tr('logIn') }, { key: 'register', label: tr('createAccount') }]} value={mode}
            onChange={(k) => { setMode(k as any); setErr(null); }} />
          <Field label={tr('email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
          <View>
            <Field label={tr('password')} value={password} onChangeText={setPassword} secureTextEntry={!show} autoCapitalize="none" />
            <Text onPress={() => setShow(!show)} accessibilityRole="button" style={{ position: 'absolute', right: 14, top: 18, fontFamily: F.label, fontSize: 10, letterSpacing: 1.4, color: C.accent }}>
              {show ? tr('hidePw') : tr('showPw')}
            </Text>
          </View>
          {mode === 'register' && (
            <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
              <Switch value={consent} onValueChange={setConsent} trackColor={{ true: C.accent }} thumbColor="#fff" />
              <Text style={[s.muted, { flex: 1 }]}>{tr('consent')}</Text>
            </View>
          )}
          <ErrorText>{err}</ErrorText>
          <Button title={mode === 'login' ? tr('logIn') : tr('createAccount')} onPress={submit} busy={busy}
            disabled={!email || password.length < 10 || (mode === 'register' && !consent)} />
          <View style={{ borderTopWidth: 1, borderColor: C.line, paddingTop: 16, gap: 14 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <View style={{ flex: 1, gap: 3 }}>
                <K size={10}>Server</K>
                <Text numberOfLines={1} style={{ fontFamily: F.mono, fontSize: 12, color: C.fg }}>{server}</Text>
              </View>
              <Button kind="tonal" title={editServer ? 'Done' : 'Change'} onPress={() => setEditServer(!editServer)} style={{ height: 40, borderRadius: 10, paddingHorizontal: 12 }} />
            </View>
            {editServer && <Field label="Server address" value={server} onChangeText={setServer} autoCapitalize="none" autoCorrect={false} keyboardType="url" mono />}
          </View>
        </ScrollView>
      </SheetIn>
    </KeyboardAvoidingView>
  );
}
