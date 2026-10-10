import React, { useMemo, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path } from 'react-native-svg';
import { FadeIn, Press } from '../anim';
import { api, getBaseUrl, setBaseUrl, setToken } from '../api';
import { Button, ErrorText, LangToggle, Segmented, s } from '../components/ui';
import { useT } from '../i18n';
import { C, F } from '../theme';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function strength(pw: string): 0 | 1 | 2 | 3 {
  if (pw.length < 10) return pw.length === 0 ? 0 : 1;
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  return pw.length >= 14 && classes >= 3 ? 3 : classes >= 2 ? 2 : 1;
}

/** Underlined-card input with an inline label, clear focus ring and an optional trailing action. */
function Input({ label, error, trailing, ...rest }: any) {
  const [focus, setFocus] = useState(false);
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ fontFamily: F.bodyMed, fontSize: 13, color: C.muted }}>{label}</Text>
      <View style={{ height: 54, borderRadius: 14, backgroundColor: C.surface, borderWidth: focus ? 2 : 1, borderColor: error ? C.bad : focus ? C.accent : C.line,
        flexDirection: 'row', alignItems: 'center', paddingLeft: 16, paddingRight: trailing ? 6 : 16 }}>
        <TextInput {...rest} accessibilityLabel={label} placeholderTextColor="#98A39C" onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          style={{ flex: 1, fontFamily: F.body, fontSize: 16, color: C.fg, paddingVertical: 0 }} />
        {trailing}
      </View>
      {error ? <Text style={{ fontFamily: F.bodyMed, fontSize: 12, color: C.bad }}>{error}</Text> : null}
    </View>
  );
}

const Perk = ({ text }: { text: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
    <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: C.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={12} height={12} viewBox="0 0 24 24"><Path d="M5 12.5l4.5 4.5L19 7.5" stroke={C.accent} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" fill="none" /></Svg>
    </View>
    <Text style={{ fontFamily: F.bodyMed, fontSize: 14, color: C.fg }}>{text}</Text>
  </View>
);

export default function AuthScreen({ onDone }: { onDone: () => void }) {
  const { t: tr } = useT();
  const { top, bottom } = useSafeAreaInsets();
  const [server, setServer] = useState(getBaseUrl());
  const [adv, setAdv] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [consent, setConsent] = useState(false);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const pwRef = useRef<TextInput>(null);

  const emailOk = EMAIL_RE.test(email.trim());
  const st = strength(password);
  const canSubmit = emailOk && password.length >= 10 && (mode === 'login' || consent);
  const stColor = st === 3 ? C.accent : st === 2 ? C.gold : C.bad;
  const stLabel = st === 3 ? tr('pwStrong') : st === 2 ? tr('pwOk') : tr('pwWeak');
  const emailErr = useMemo(() => (touched && email && !emailOk ? tr('badEmail') : undefined), [touched, email, emailOk, tr]);

  async function submit() {
    if (!canSubmit || busy) return;
    setBusy(true); setErr(null);
    try {
      await setBaseUrl(server);
      const res = mode === 'login' ? await api.login(email.trim(), password) : await api.register(email.trim(), password);
      await setToken(res.access_token);
      onDone();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1, backgroundColor: C.bg }}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingTop: top + 12, paddingHorizontal: 22, paddingBottom: Math.max(bottom, 16) + 24, gap: 22 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Svg width={34} height={34} viewBox="0 0 64 64">
              <Circle cx={32} cy={32} r={24} stroke={C.track} strokeWidth={9} fill="none" />
              <Circle cx={32} cy={32} r={24} stroke={C.accent} strokeWidth={9} fill="none" strokeLinecap="round" strokeDasharray="108 151" transform="rotate(-90 32 32)" />
            </Svg>
            <Text style={{ fontFamily: F.display, fontSize: 18, color: C.fg }}>Health Companion</Text>
          </View>
          <LangToggle />
        </View>

        <FadeIn>
          <View style={{ gap: 14 }}>
            <Text style={{ fontFamily: F.display, fontSize: 34, lineHeight: 40, color: C.fg }}>{tr('authHeadline')}</Text>
            <View style={{ gap: 10 }}>
              <Perk text={tr('authB1')} /><Perk text={tr('authB2')} /><Perk text={tr('authB3')} />
            </View>
          </View>
        </FadeIn>

        <FadeIn delay={120}>
          <View style={{ backgroundColor: C.surface, borderRadius: 24, padding: 18, gap: 16, borderWidth: 1, borderColor: C.line }}>
            <Segmented options={[{ key: 'login', label: tr('logIn') }, { key: 'register', label: tr('createAccount') }]} value={mode}
              onChange={(k) => { setMode(k as any); setErr(null); }} />
            <Text style={{ fontFamily: F.display, fontSize: 22, color: C.fg }}>{mode === 'login' ? tr('welcomeBack') : tr('createYour')}</Text>

            <Input label={tr('email')} value={email} onChangeText={setEmail} onBlur={() => setTouched(true)} error={emailErr} autoCapitalize="none"
              keyboardType="email-address" autoComplete="email" textContentType="emailAddress" returnKeyType="next" onSubmitEditing={() => pwRef.current?.focus()} />

            <View style={{ gap: 8 }}>
              <Input ref={pwRef} label={tr('password')} value={password} onChangeText={setPassword} secureTextEntry={!show} autoCapitalize="none"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'} textContentType={mode === 'login' ? 'password' : 'newPassword'}
                returnKeyType="go" onSubmitEditing={submit}
                trailing={<Press accessibilityRole="button" accessibilityLabel={show ? tr('hidePw') : tr('showPw')} onPress={() => setShow(!show)} style={{ paddingHorizontal: 12, height: 40, justifyContent: 'center' }}>
                  <Text style={{ fontFamily: F.bodyBold, fontSize: 13, color: C.accent }}>{show ? tr('hidePw') : tr('showPw')}</Text></Press>} />
              {mode === 'register' && (
                <View style={{ gap: 6 }}>
                  <View style={{ flexDirection: 'row', gap: 4 }}>
                    {[1, 2, 3].map((i) => <View key={i} style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: st >= i ? stColor : C.track }} />)}
                  </View>
                  <Text style={s.muted}>{password.length === 0 ? tr('pwNeed') : password.length < 10 ? tr('pwNeed') : stLabel}</Text>
                </View>
              )}
            </View>

            {mode === 'register' && (
              <Press accessibilityRole="checkbox" accessibilityState={{ checked: consent }} onPress={() => setConsent(!consent)} style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
                <View style={{ width: 24, height: 24, borderRadius: 7, borderWidth: 2, borderColor: consent ? C.accent : '#98A39C', backgroundColor: consent ? C.accent : 'transparent', alignItems: 'center', justifyContent: 'center', marginTop: 1 }}>
                  {consent && <Svg width={14} height={14} viewBox="0 0 24 24"><Path d="M5 12.5l4.5 4.5L19 7.5" stroke="#fff" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round" fill="none" /></Svg>}
                </View>
                <Text style={[s.muted, { flex: 1 }]}>{tr('consent')}</Text>
              </Press>
            )}

            <ErrorText>{err}</ErrorText>
            <Button title={mode === 'login' ? tr('logIn') : tr('createAccount')} onPress={submit} busy={busy} disabled={!canSubmit} />
            <Press accessibilityRole="button" onPress={() => { setMode(mode === 'login' ? 'register' : 'login'); setErr(null); }} style={{ minHeight: 44, alignItems: 'center', justifyContent: 'center' }}>
              <Text style={{ fontFamily: F.bodyBold, fontSize: 14, color: C.accent }}>{mode === 'login' ? tr('newHere') : tr('haveOne')}</Text>
            </Press>
          </View>
        </FadeIn>

        <Text style={[s.muted, { textAlign: 'center' }]}>{tr('privacyNote')}</Text>

        <View style={{ alignItems: 'center', gap: 10 }}>
          <Press accessibilityRole="button" onPress={() => setAdv(!adv)} style={{ minHeight: 40, justifyContent: 'center' }}>
            <Text style={{ fontFamily: F.bodyMed, fontSize: 12, color: C.muted }}>{tr('advanced')} {adv ? '▴' : '▾'}</Text>
          </Press>
          {adv && <Input label={tr('serverAddr')} value={server} onChangeText={setServer} autoCapitalize="none" autoCorrect={false} keyboardType="url" />}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
