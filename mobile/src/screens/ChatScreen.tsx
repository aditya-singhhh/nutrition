import React, { useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Text, View } from 'react-native';
import { api } from '../api';
import { Button, ErrorText, Field, s } from '../components/ui';
import { C } from '../theme';

type Msg = { id: number; role: 'user' | 'assistant'; text: string; warn?: boolean };

export default function ChatScreen() {
  const [msgs, setMsgs] = useState<Msg[]>([{
    id: 0, role: 'assistant',
    text: 'Hi! Ask about a dish like "Is masala dosa ok for me?", paste a product barcode, ask what to eat next, or how much you have eaten today.',
  }]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const session = useRef<number | undefined>(undefined);
  const idRef = useRef(1);

  async function send() {
    const m = text.trim();
    if (!m) return;
    setText('');
    setErr(null);
    setMsgs((x) => [...x, { id: idRef.current++, role: 'user', text: m }]);
    setBusy(true);
    try {
      const r: any = await api.chat(m, session.current);
      session.current = r.session_id;
      setMsgs((x) => [...x, { id: idRef.current++, role: 'assistant', text: r.reply, warn: r.safety_level !== 'ok' }]);
    } catch (e: any) {
      setErr(e.message);
    } finally { setBusy(false); }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1, backgroundColor: C.bg }}>
      <FlatList
        data={msgs}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={{ padding: 16, gap: 10, paddingTop: 48 }}
        ListHeaderComponent={<Text style={[s.h1, { marginBottom: 6 }]}>Ask</Text>}
        renderItem={({ item }) => (
          <View style={{
            alignSelf: item.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '88%', padding: 12, borderRadius: 14,
            backgroundColor: item.role === 'user' ? C.accent : item.warn ? C.badSoft : C.surface,
            borderWidth: item.role === 'user' ? 0 : 1, borderColor: C.line,
          }}>
            <Text style={{ color: item.role === 'user' ? '#fff' : C.fg, fontSize: 14, lineHeight: 20 }}>{item.text}</Text>
          </View>
        )}
      />
      <View style={{ padding: 12, gap: 8, borderTopWidth: 1, borderColor: C.line, backgroundColor: C.surface }}>
        <ErrorText>{err}</ErrorText>
        <Field label="Message" value={text} onChangeText={setText} maxLength={1000} onSubmitEditing={send} returnKeyType="send" />
        <Button title="Send" onPress={send} busy={busy} disabled={!text.trim()} />
      </View>
    </KeyboardAvoidingView>
  );
}
