import { CameraView, useCameraPermissions } from 'expo-camera';
import React, { useRef, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { api } from '../api';
import ResultView from '../components/ResultView';
import { Button, Card, Chip, ErrorText, Field, s } from '../components/ui';
import { C } from '../theme';

type Mode = 'barcode' | 'search';
type Target = { food_slug?: string; barcode?: string };

export default function ScanScreen({ onLogged }: { onLogged: () => void }) {
  const [mode, setMode] = useState<Mode>('barcode');
  const [perm, askPerm] = useCameraPermissions();
  const [result, setResult] = useState<any>(null);
  const [target, setTarget] = useState<Target | null>(null);
  const [manual, setManual] = useState('');
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const lock = useRef(false);

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try { return await fn(); } catch (e: any) {
      const d = e.detail;
      setErr(d && typeof d === 'object' && 'message' in d ? (d as any).message : e.message);
    } finally { setBusy(false); }
  }

  async function scan(code: string) {
    const r = await run(() => api.scanBarcode(code));
    if (r) { setResult(r); setTarget({ barcode: r.barcode }); }
    lock.current = false;
  }

  async function pick(slug: string) {
    const r = await run(() => api.analyzeFood(slug));
    if (r) { setResult(r); setTarget({ food_slug: slug }); }
  }

  async function log() {
    if (!target) return;
    const ok = await run(() => api.logMeal(target));
    if (ok) { setMsg('Logged to today.'); onLogged(); }
  }

  if (result) {
    return (
      <ScrollView style={{ backgroundColor: C.bg }} contentContainerStyle={{ padding: 16, gap: 12, paddingTop: 48 }}>
        <ResultView r={result} />
        {msg && <Text style={{ color: C.ok, fontWeight: '600' }}>{msg}</Text>}
        <ErrorText>{err}</ErrorText>
        <Button title="Log 1 serving" onPress={log} busy={busy} />
        <Button kind="ghost" title="Scan something else" onPress={() => { setResult(null); setTarget(null); setMsg(null); }} />
      </ScrollView>
    );
  }

  return (
    <ScrollView style={{ backgroundColor: C.bg }} contentContainerStyle={{ padding: 16, gap: 12, paddingTop: 48 }}
      keyboardShouldPersistTaps="handled">
      <Text style={s.h1}>Scan</Text>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Chip label="Barcode" on={mode === 'barcode'} onPress={() => setMode('barcode')} />
        <Chip label="Search dishes" on={mode === 'search'} onPress={() => setMode('search')} />
      </View>
      <ErrorText>{err}</ErrorText>

      {mode === 'barcode' && (
        <>
          {!perm ? null : !perm.granted ? (
            <Card>
              <Text style={s.body}>Camera access is needed to scan barcodes. You can also type the number below.</Text>
              <Button title="Allow camera" onPress={askPerm} />
            </Card>
          ) : (
            <View style={{ height: 260, borderRadius: 12, overflow: 'hidden' }}>
              <CameraView
                style={{ flex: 1 }}
                barcodeScannerSettings={{ barcodeTypes: ['ean13', 'ean8', 'upc_a'] }}
                onBarcodeScanned={({ data }) => {
                  if (lock.current) return;
                  lock.current = true;
                  scan(data);
                }}
              />
            </View>
          )}
          <Field label="Or type the barcode number" value={manual} onChangeText={setManual} keyboardType="number-pad" />
          <Button title="Look up" onPress={() => scan(manual)} busy={busy} disabled={manual.length < 8} />
        </>
      )}

      {mode === 'search' && (
        <>
          <Field label="Dish name (e.g. masala dosa, dal, poha)" value={query} onChangeText={setQuery} autoCapitalize="none" />
          <Button title="Search" busy={busy} disabled={!query.trim()}
            onPress={async () => { const r = await run(() => api.searchFoods(query.trim())); if (r) setHits(r.items); }} />
          {hits.map((h) => (
            <Card key={h.slug}>
              <Text style={s.h2}>{h.name}</Text>
              <Text style={s.muted}>{h.region} · {h.serving.label}</Text>
              <Button kind="ghost" title="See details" onPress={() => pick(h.slug)} />
            </Card>
          ))}
        </>
      )}
      <Text style={s.muted}>Food-photo and label scanning are not enabled yet.</Text>
    </ScrollView>
  );
}
