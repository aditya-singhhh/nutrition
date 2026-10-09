import React, { useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { FadeIn, Press } from '../anim';
import { api } from '../api';
import { Display, ErrorText, K } from '../components/ui';
import { C, F } from '../theme';

type Msg = { id: number; role: 'user' | 'assistant'; text: string; warn?: boolean };
const SUGGEST = ['Is masala dosa ok for me?', 'What should I eat next?', 'How much protein today?'];

export default function ChatScreen() {
  const { top } = useSafeAreaInsets();
  const [msgs, setMsgs] = useState<Msg[]>([{ id: 0, role: 'assistant', text: 'Hi! Ask about a dish, paste a barcode, ask what to eat next, or how much you have eaten today.' }]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const session = useRef<number | undefined>(undefined);
  const idRef = useRef(1);
  const list = useRef<FlatList<Msg>>(null);

  async function send(raw?: string) {
    const m = (raw ?? text).trim();
    if (!m || busy) return;
    setText(''); setErr(null);
    setMsgs((x) => [...x, { id: idRef.current++, role: 'user', text: m }]);
    setBusy(true);
    try {
      const r: any = await api.chat(m, session.current);
      session.current = r.session_id;
      setMsgs((x) => [...x, { id: idRef.current++, role: 'assistant', text: r.reply, warn: r.safety_level !== 'ok' }]);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <KeyboardAvoidingView behavior="padding" style={{ flex: 1, backgroundColor: C.bg }}>
      <FlatList
        ref={list} data={msgs} keyExtractor={(m) => String(m.id)} onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        contentContainerStyle={{ padding: 20, paddingTop: top + 20, gap: 10 }}
        ListHeaderComponent={<Display size={52} style={{ marginBottom: 10 }}>Ask</Display>}
        ListFooterComponent={busy ? <K style={{ marginTop: 6 }}>Thinking…</K> : null}
        renderItem={({ item }) => {
          const me = item.role === 'user';
          return (
            <FadeIn y={10} style={{ alignSelf: me ? 'flex-end' : 'flex-start', maxWidth: '88%' }}>
              <View style={{ padding: 14, borderRadius: 20, borderBottomRightRadius: me ? 6 : 20, borderBottomLeftRadius: me ? 20 : 6,
                backgroundColor: me ? C.accent : item.warn ? C.badSoft : C.surface }}>
                {item.warn && <K color={C.bad} style={{ marginBottom: 6 }}>Important</K>}
                <Text style={{ fontFamily: F.body, fontSize: 15, lineHeight: 21, color: me ? '#fff' : C.fg }}>{item.text}</Text>
              </View>
            </FadeIn>
          );
        }}
      />
      <View style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12, gap: 10 }}>
        <ErrorText>{err}</ErrorText>
        {msgs.length < 2 && (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {SUGGEST.map((q) => (
              <Press key={q} onPress={() => send(q)} style={{ paddingHorizontal: 14, minHeight: 40, borderRadius: 12, justifyContent: 'center', backgroundColor: C.surface, borderWidth: 1, borderColor: C.line }}>
                <Text style={{ fontFamily: F.bodyMed, fontSize: 13, color: C.fg }}>{q}</Text>
              </Press>
            ))}
          </View>
        )}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={{ flex: 1, minHeight: 52, borderRadius: 26, backgroundColor: C.surface, paddingHorizontal: 18, justifyContent: 'center' }}>
            <TextInput value={text} onChangeText={setText} placeholder="Ask about food…" placeholderTextColor="#7A8A80" maxLength={1000}
              onSubmitEditing={() => send()} returnKeyType="send" accessibilityLabel="Message"
              style={{ fontFamily: F.body, fontSize: 16, color: C.fg, paddingVertical: 8 }} />
          </View>
          <Press accessibilityRole="button" accessibilityLabel="Send" disabled={!text.trim() || busy} onPress={() => send()}
            style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', opacity: text.trim() && !busy ? 1 : 0.45 }}>
            <Svg width={22} height={22} viewBox="0 0 24 24"><Path d="M4 12l16-8-6 16-2-7z" fill="#fff" /></Svg>
          </Press>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}
