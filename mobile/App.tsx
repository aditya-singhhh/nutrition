import { Archivo_700Bold } from '@expo-google-fonts/archivo/700Bold';
import { ArchivoNarrow_700Bold } from '@expo-google-fonts/archivo-narrow/700Bold';
import { InstrumentSans_400Regular } from '@expo-google-fonts/instrument-sans/400Regular';
import { InstrumentSans_500Medium } from '@expo-google-fonts/instrument-sans/500Medium';
import { InstrumentSans_600SemiBold } from '@expo-google-fonts/instrument-sans/600SemiBold';
import { JetBrainsMono_500Medium } from '@expo-google-fonts/jetbrains-mono/500Medium';
import { useFonts } from 'expo-font';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, BackHandler, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { FadeIn } from './src/anim';
import { loadSession } from './src/api';
import TabBar, { Tab } from './src/components/TabBar';
import AuthScreen from './src/screens/AuthScreen';
import ChatScreen from './src/screens/ChatScreen';
import HomeScreen from './src/screens/HomeScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import ScanScreen from './src/screens/ScanScreen';
import { C } from './src/theme';

export default function App() {
  const [fontsReady] = useFonts({ Archivo_700Bold, ArchivoNarrow_700Bold, InstrumentSans_400Regular, InstrumentSans_500Medium,
    InstrumentSans_600SemiBold, JetBrainsMono_500Medium });
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [tab, setTab] = useState<Tab>('home');
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = () => setRefreshKey((k) => k + 1);

  useEffect(() => { loadSession().then((a) => { setAuthed(a); setReady(true); }); }, []);
  // Android back: go to Home first, then let the system close the app.
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => { if (authed && tab !== 'home') { setTab('home'); return true; } return false; });
    return () => sub.remove();
  }, [authed, tab]);

  let body: React.ReactNode;
  if (!ready || !fontsReady) body = <View style={{ flex: 1, justifyContent: 'center', backgroundColor: C.ink }}><ActivityIndicator color={C.gold} /></View>;
  else if (!authed) body = <><StatusBar style="light" /><AuthScreen onDone={() => { setTab('home'); setAuthed(true); }} /></>;
  else body = (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <StatusBar style={tab === 'scan' ? 'light' : 'dark'} />
      <FadeIn key={tab} y={10} style={{ flex: 1 }}>
        {tab === 'home' && <HomeScreen refreshKey={refreshKey} onScan={() => setTab('scan')} />}
        {tab === 'scan' && <ScanScreen onLogged={bump} onClose={() => setTab('home')} />}
        {tab === 'ask' && <ChatScreen />}
        {tab === 'profile' && <ProfileScreen onLogout={() => setAuthed(false)} onSaved={bump} />}
      </FadeIn>
      <TabBar tab={tab} onChange={setTab} />
    </View>
  );
  return <SafeAreaProvider>{body}</SafeAreaProvider>;
}
