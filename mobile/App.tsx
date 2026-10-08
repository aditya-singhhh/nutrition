import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, SafeAreaView, Text, View } from 'react-native';
import { loadSession } from './src/api';
import AuthScreen from './src/screens/AuthScreen';
import ChatScreen from './src/screens/ChatScreen';
import HomeScreen from './src/screens/HomeScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import ScanScreen from './src/screens/ScanScreen';
import { C } from './src/theme';

type Tab = 'home' | 'scan' | 'ask' | 'profile';
const TABS: { key: Tab; label: string }[] = [
  { key: 'home', label: 'Home' }, { key: 'scan', label: 'Scan' }, { key: 'ask', label: 'Ask' }, { key: 'profile', label: 'Profile' },
];

export default function App() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [tab, setTab] = useState<Tab>('home');
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = () => setRefreshKey((k) => k + 1);

  useEffect(() => { loadSession().then((a) => { setAuthed(a); setReady(true); }); }, []);

  if (!ready) return <View style={{ flex: 1, justifyContent: 'center', backgroundColor: C.bg }}><ActivityIndicator color={C.accent} /></View>;
  if (!authed) return <><StatusBar style="dark" /><AuthScreen onDone={() => { setTab('home'); setAuthed(true); }} /></>;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }}>
      <StatusBar style="dark" />
      <View style={{ flex: 1 }}>
        {tab === 'home' && <HomeScreen refreshKey={refreshKey} />}
        {tab === 'scan' && <ScanScreen onLogged={bump} />}
        {tab === 'ask' && <ChatScreen />}
        {tab === 'profile' && <ProfileScreen onLogout={() => setAuthed(false)} onSaved={bump} />}
      </View>
      <View style={{ flexDirection: 'row', borderTopWidth: 1, borderColor: C.line, backgroundColor: C.surface }}>
        {TABS.map((t) => (
          <Pressable key={t.key} onPress={() => setTab(t.key)} accessibilityRole="tab" accessibilityState={{ selected: tab === t.key }}
            style={{ flex: 1, paddingVertical: 14, alignItems: 'center' }}>
            <Text style={{ color: tab === t.key ? C.accent : C.muted, fontWeight: tab === t.key ? '700' : '500', fontSize: 13 }}>{t.label}</Text>
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
  );
}
