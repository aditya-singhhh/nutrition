import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Switch, Text, View } from 'react-native';
import { api, getBaseUrl, setBaseUrl, setToken } from '../api';
import { Button, ErrorText, Field, s } from '../components/ui';
import { C } from '../theme';

export default function AuthScreen({ onDone }: { onDone: () => void }) {
  const [server, setServer] = useState(getBaseUrl());
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [consent, setConsent] = useState(false);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      await setBaseUrl(server);
      const res = mode === 'login' ? await api.login(email.trim(), password) : await api.register(email.trim(), password);
      await setToken(res.access_token);
      onDone();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1, backgroundColor: C.bg }}>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 14, paddingTop: 64 }} keyboardShouldPersistTaps="handled">
        <Text style={s.h1}>Health Companion</Text>
        <Text style={s.muted}>Scan food, understand it, and see what fits your health.</Text>
        <Field label="Server address" value={server} onChangeText={setServer} autoCapitalize="none" autoCorrect={false}
          keyboardType="url" />
        <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" />
        <Field label="Password (10+ characters)" value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" />
        {mode === 'register' && (
          <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
            <Switch value={consent} onValueChange={setConsent} trackColor={{ true: C.accent }} />
            <Text style={[s.body, { flex: 1 }]}>
              I agree to the terms and consent to my health information being processed to personalise nutrition guidance.
            </Text>
          </View>
        )}
        <ErrorText>{err}</ErrorText>
        <Button title={mode === 'login' ? 'Log in' : 'Create account'} onPress={submit} busy={busy}
          disabled={!email || password.length < 10 || (mode === 'register' && !consent)} />
        <Button kind="ghost" title={mode === 'login' ? 'New here? Create an account' : 'Have an account? Log in'}
          onPress={() => { setMode(mode === 'login' ? 'register' : 'login'); setErr(null); }} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
