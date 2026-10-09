import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Haptics from 'expo-haptics';
import * as ImagePicker from 'expo-image-picker';
import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, BackHandler, Image, KeyboardAvoidingView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { FadeIn, Laser, Press, Pulse, SheetIn } from '../anim';
import { api } from '../api';
import { useT } from '../i18n';
import ResultView from '../components/ResultView';
import Screen from '../components/Screen';
import { Button, Card, Display, ErrorText, Field, K, Tag, s } from '../components/ui';
import { C, F } from '../theme';

type Mode = 'scan' | 'type' | 'search';
type Target = { food_slug?: string; barcode?: string };
type PhotoItem = { slug: string; name: string; conf: number; sure: boolean; lo: number; hi: number; kcal: [number, number]; size: 0 | 1 | 2; on: boolean };
const gramsFor = (i: PhotoItem) => [i.lo, (i.lo + i.hi) / 2, i.hi][i.size];
const kcalFor = (i: PhotoItem) => [i.kcal[0], (i.kcal[0] + i.kcal[1]) / 2, i.kcal[1]][i.size];

const Corner = ({ style }: { style: any }) => <View style={[{ position: 'absolute', width: 32, height: 32, borderColor: C.gold }, style]} />;
const IconBtn = ({ label, onPress, children }: { label: string; onPress: () => void; children: React.ReactNode }) => (
  <Press accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
    style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: 'rgba(10,18,14,.55)', alignItems: 'center', justifyContent: 'center' }}>{children}</Press>
);

export default function ScanScreen({ onLogged, onClose }: { onLogged: () => void; onClose: () => void }) {
  const { top, bottom } = useSafeAreaInsets();
  const { t: tr } = useT();
  const [mode, setMode] = useState<Mode>('scan');
  const [perm, askPerm] = useCameraPermissions();
  const [torch, setTorch] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [target, setTarget] = useState<Target | null>(null);
  const [photo, setPhoto] = useState<{ id: number; items: PhotoItem[]; unrecognised: string[] } | null>(null);
  const [cands, setCands] = useState<{ recognised: string; list: any[] } | null>(null);
  const [frozen, setFrozen] = useState<string | null>(null); // the picture being analysed, shown in place of the live camera
  const [manual, setManual] = useState('');
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [missingCode, setMissingCode] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const lock = useRef(false);
  useEffect(() => {
    setSlow(false);
    if (!busy) return;
    const t = setTimeout(() => setSlow(true), 8000);
    return () => clearTimeout(t);
  }, [busy]);
  const cam = useRef<CameraView>(null);

  const inResult = !!result || !!photo;
  const reset = () => { setResult(null); setTarget(null); setPhoto(null); setMsg(null); setErr(null); setNotFound(false); lock.current = false; };
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => { if (inResult) { reset(); return true; } return false; });
    return () => sub.remove();
  }, [inResult]);

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true); setErr(null); setMsg(null); setNotFound(false);
    try { return await fn(); } catch (e: any) {
      const d = e.detail;
      if (d && typeof d === 'object' && d.code === 'product_not_found') setNotFound(true);
      setErr(d && typeof d === 'object' && 'message' in d ? d.message : e.message);
    } finally { setBusy(false); }
  }

  async function scan(code: string) {
    const r = await run(() => api.scanBarcode(code));
    if (!r) setMissingCode(code);
    if (r) {
      setMissingCode(null); Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {}); setResult(r); setTarget({ barcode: r.barcode }); }
    lock.current = false;
  }
  async function pick(slug: string) {
    const r = await run(() => api.analyzeFood(slug));
    if (r) { setResult(r); setTarget({ food_slug: slug }); }
  }
  async function analyse(b64: string | null | undefined, uri?: string) {
    if (!b64) { setErr('Could not read that picture. Please try again.'); return; }
    if (uri) setFrozen(uri);
    const r: any = await run(() => api.scanSmart(b64, missingCode ?? undefined));
    setFrozen(null);
    if (!r) return;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    if (r.kind === 'candidates') { setCands({ recognised: r.recognised ?? '', list: r.candidates ?? [] }); return; }
    if (r.kind === 'product') { setResult(r); setTarget({ barcode: r.barcode }); }
    else if (r.kind === 'label') setResult({ ...r, name: 'Scanned label' });
    else setPhoto({
      id: r.prediction_id, unrecognised: r.unrecognised ?? [],
      items: r.items.map((i: any): PhotoItem => ({
        slug: i.food.slug, name: i.food.name, conf: i.confidence, sure: !i.needs_confirmation, on: true, size: 1,
        lo: i.portion_g_range[0], hi: i.portion_g_range[1], kcal: [i.nutrition_range.min.energy_kcal ?? 0, i.nutrition_range.max.energy_kcal ?? 0] })),
    });
  }
  async function snap() {
    if (!cam.current || busy) return;
    const pic = await run(async () => cam.current!.takePictureAsync({ quality: 0.4, base64: true, skipProcessing: true }));
    if (!pic) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    await analyse(pic.base64, pic.uri);
  }
  async function fromGallery() {
    if (busy) return;
    const res = await run(() => ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.4, base64: true }));
    if (!res || res.canceled) return;
    await analyse(res.assets?.[0]?.base64, res.assets?.[0]?.uri);
  }
  async function log() {
    if (!target) return;
    if (await run(() => api.logMeal(target))) { setMsg('Logged to today.'); onLogged(); }
  }
  async function logPhoto() {
    if (!photo) return;
    const chosen = photo.items.filter((i) => i.on);
    if (!chosen.length) return;
    const ok = await run(() => api.logPhotoMeal(photo.id, chosen.map((i) => ({ food_slug: i.slug, grams: Math.round(gramsFor(i)), grams_min: i.lo, grams_max: i.hi }))));
    if (ok) {
      api.feedback(photo.id, chosen.length === photo.items.length, chosen.map((i) => ({ food_slug: i.slug, grams: Math.round(gramsFor(i)) }))).catch(() => {});
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      setMsg('Logged to today.'); onLogged();
    }
  }
  const setItem = (slug: string, patch: Partial<PhotoItem>) => setPhoto((p) => p && { ...p, items: p.items.map((i) => (i.slug === slug ? { ...i, ...patch } : i)) });

  /* ---------------------------------------------------------------- results */
  if (result) {
    return (
      <View style={{ flex: 1, backgroundColor: C.bg }}>
        <Screen>
          <Press accessibilityRole="button" accessibilityLabel="Back to scanner" onPress={reset} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, height: 40 }}>
            <Svg width={22} height={22} viewBox="0 0 24 24"><Path d="M15 5l-7 7 7 7" stroke={C.fg} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" fill="none" /></Svg>
            <K color={C.fg}>Scan again</K>
          </Press>
          <ResultView r={result} onOpen={(it) => (it.type === "food" ? pick(it.id) : scan(it.id))} />
          {result.extracted_text ? <Card><K>What we read from the label</K><Text style={s.muted}>{result.extracted_text}</Text></Card> : null}
          {msg && <Text style={{ color: C.accent, fontFamily: F.bodyBold }}>{msg}</Text>}
          <ErrorText>{err}</ErrorText>
        </Screen>
        {target && <View style={{ padding: 16, paddingBottom: 16, backgroundColor: C.bg, borderTopWidth: 1, borderColor: C.line }}>
          <Button title={result.nutrition_for_portion ? `${tr('logServing')} · ${Math.round(result.nutrition_for_portion.energy_kcal ?? 0)} kcal` : tr('logServing')} onPress={log} busy={busy} />
        </View>}
      </View>
    );
  }
  if (cands) {
    return (
      <View style={{ flex: 1, backgroundColor: C.bg }}>
        <Screen>
          <Button kind="tonal" title={tr('back')} onPress={() => setCands(null)} style={{ height: 44 }} />
          <FadeIn><Display size={34}>{tr('pickPack')}</Display></FadeIn>
          <Text style={s.body}>{tr('pickPackHelp', { name: cands.recognised })}</Text>
          {cands.list.map((c: any, i: number) => (
            <Press key={c.barcode + i} onPress={async () => { const code = c.barcode; setCands(null); await scan(code); }}>
              <Card>
                <Text style={[s.body, { fontFamily: F.bodyBold }]}>{c.name}{c.brand ? ` · ${c.brand}` : ''}</Text>
                <Text style={s.muted}>{[c.quantity, c.energy_kcal != null ? `${Math.round(c.energy_kcal)} kcal/100g` : null, c.sat_fat_g != null ? `sat fat ${c.sat_fat_g} g` : null, c.complete ? null : 'incomplete data'].filter(Boolean).join(' · ')}</Text>
              </Card>
            </Press>
          ))}
          <ErrorText>{err}</ErrorText>
        </Screen>
      </View>
    );
  }
  if (photo) {
    const chosen = photo.items.filter((i) => i.on);
    const total = chosen.reduce((a, i) => a + kcalFor(i), 0);
    return (
      <View style={{ flex: 1, backgroundColor: C.bg }}>
        <Screen>
          <Press accessibilityRole="button" accessibilityLabel="Back to scanner" onPress={reset} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, height: 40 }}>
            <Svg width={22} height={22} viewBox="0 0 24 24"><Path d="M15 5l-7 7 7 7" stroke={C.fg} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" fill="none" /></Svg>
            <K color={C.fg}>Retake</K>
          </Press>
          <FadeIn><Display size={40}>{photo.items.length ? `We found ${photo.items.length} item${photo.items.length > 1 ? 's' : ''}` : 'No known dish found'}</Display></FadeIn>
          <Text style={s.muted}>Portions are estimates, not exact weights. Check and correct before logging.</Text>
          {photo.items.map((i, n) => (
            <FadeIn key={i.slug} delay={n * 90}>
              <Card style={{ opacity: i.on ? 1 : 0.5, borderWidth: i.sure ? 0 : 2, borderColor: C.gold }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                  <Text style={{ flex: 1, fontFamily: F.bodyBold, fontSize: 18, color: C.fg }}>{i.name}</Text>
                  <Tag tone={i.sure ? 'ok' : 'warn'} label={i.sure ? `${Math.round(i.conf * 100)}% sure` : 'Not sure · confirm'} />
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <View style={{ gap: 4 }}>
                    <K>Portion</K>
                    <Text style={{ fontFamily: F.display, fontSize: 28, color: C.fg }}>{Math.round(i.lo)}–{Math.round(i.hi)} G</Text>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 6 }}>
                    {(['S', 'M', 'L'] as const).map((l, k) => (
                      <Press key={l} accessibilityRole="button" accessibilityLabel={`Size ${l}`} accessibilityState={{ selected: i.size === k }} onPress={() => setItem(i.slug, { size: k as 0 | 1 | 2 })}
                        style={{ width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: i.size === k ? C.ink : C.bg }}>
                        <K size={13} color={i.size === k ? '#fff' : C.fg}>{l}</K>
                      </Press>
                    ))}
                  </View>
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderTopWidth: 1, borderColor: C.line, paddingTop: 10 }}>
                  <Text style={s.muted}>≈ <Text style={{ fontFamily: F.bodyBold, color: C.fg }}>{Math.round(kcalFor(i))} kcal</Text></Text>
                  <Press accessibilityRole="button" onPress={() => setItem(i.slug, { on: !i.on })}><K color={i.on ? C.bad : C.accent}>{i.on ? 'Remove' : 'Add back'}</K></Press>
                </View>
              </Card>
            </FadeIn>
          ))}
          {photo.unrecognised.length > 0 && <Card tone="warn"><Text style={s.body}>We saw {photo.unrecognised.join(', ')}, but {photo.unrecognised.length > 1 ? 'they are' : 'it is'} not in our food list yet, so we won't guess numbers. Try Search to find something close.</Text></Card>}
          {msg && <Text style={{ color: C.accent, fontFamily: F.bodyBold }}>{msg}</Text>}
          <ErrorText>{err}</ErrorText>
        </Screen>
        <View style={{ padding: 16, gap: 10, backgroundColor: C.bg, borderTopWidth: 1, borderColor: C.line }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <K>Estimated total</K>
            <Text style={{ fontFamily: F.display, fontSize: 28, color: C.fg }}>{Math.round(total)} <Text style={{ fontSize: 13, color: C.muted }}>KCAL</Text></Text>
          </View>
          <Button title="Log this meal" onPress={logPhoto} busy={busy} disabled={!chosen.length || !!msg} />
        </View>
      </View>
    );
  }

  /* ---------------------------------------------------------------- camera / search */
  const camMode = mode !== 'search';
  const camOk = camMode && perm?.granted;
  const bsPad = Math.max(bottom, 12) + 16;
  const lookup = async () => { const r = await run(() => api.searchFoods(query.trim())); if (r) setHits(r.items); };
  return (
    <KeyboardAvoidingView behavior="padding" style={{ flex: 1, backgroundColor: '#0A120E' }}>
      {camOk && (
        <CameraView ref={cam} style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} enableTorch={torch} facing="back"
          barcodeScannerSettings={{ barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'] }}
          onBarcodeScanned={({ data }) => { if (lock.current || busy) return; lock.current = true; scan(data); }} />
      )}
      {frozen && <Image source={{ uri: frozen }} resizeMode="cover" accessibilityLabel="Picture being analysed" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} />}
      {frozen && <View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.25)' }} />}
      <View style={{ paddingTop: top + 8, paddingHorizontal: 8, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <IconBtn label="Close scanner" onPress={onClose}><Svg width={24} height={24} viewBox="0 0 24 24"><Path d="M6 6l12 12M18 6L6 18" stroke="#fff" strokeWidth={2} strokeLinecap="round" /></Svg></IconBtn>
        {camOk ? <IconBtn label="Torch" onPress={() => setTorch(!torch)}><Svg width={22} height={22} viewBox="0 0 24 24"><Path d="M13 2L4 14h7l-1 8 9-12h-7z" stroke={torch ? C.gold : '#fff'} fill={torch ? C.gold : 'none'} strokeWidth={2} strokeLinejoin="round" /></Svg></IconBtn> : <View />}
      </View>

      {camMode && !perm?.granted && (
        <View style={{ flex: 1, padding: 24, justifyContent: 'center', gap: 16 }}>
          <Display size={34} color="#fff">{tr('cameraNeeded')}</Display>
          <Text style={{ fontFamily: F.body, fontSize: 15, color: C.onInk }}>{tr('cameraWhy')}</Text>
          <Button title={tr('allowCamera')} onPress={askPerm} />
        </View>
      )}
      {camOk && !frozen && (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16 }} pointerEvents="none">
          <Pulse style={{ width: 300, height: 220 }}>
            <Corner style={{ left: 0, top: 0, borderLeftWidth: 4, borderTopWidth: 4, borderTopLeftRadius: 14 }} />
            <Corner style={{ right: 0, top: 0, borderRightWidth: 4, borderTopWidth: 4, borderTopRightRadius: 14 }} />
            <Corner style={{ left: 0, bottom: 0, borderLeftWidth: 4, borderBottomWidth: 4, borderBottomLeftRadius: 14 }} />
            <Corner style={{ right: 0, bottom: 0, borderRightWidth: 4, borderBottomWidth: 4, borderBottomRightRadius: 14 }} />
            <Laser height={220} color={C.gold} />
          </Pulse>
          <View style={{ alignItems: 'center', gap: 6, paddingHorizontal: 24 }}>
            <K color="#fff" style={{ textShadowColor: '#000', textShadowRadius: 6, textAlign: 'center' }}>{tr('point')}</K>
          </View>
        </View>
      )}
      {(!camOk || !!frozen) && <View style={{ flex: 1 }} />}

      <SheetIn key={mode} style={{ backgroundColor: C.bg, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 20, paddingTop: 12, paddingBottom: bsPad, gap: 14, maxHeight: '62%' }}>
        <View style={{ alignSelf: 'center', width: 36, height: 4, borderRadius: 2, backgroundColor: '#B8C4B6' }} />
        {busy && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}><ActivityIndicator color={C.accent} /><K color={C.fg}>{slow ? tr('slow') : tr('analysing')}</K></View>}
        <ErrorText>{err}</ErrorText>
        {notFound && <Text style={s.muted}>Not found. Photograph the nutrition table on the pack.</Text>}

        {mode === 'scan' && (
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around' }}>
            <Press accessibilityRole="button" accessibilityLabel="Pick a photo from the gallery" disabled={busy} onPress={fromGallery} style={{ alignItems: 'center', gap: 6, width: 80, opacity: busy ? 0.5 : 1 }}>
              <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: C.track, alignItems: 'center', justifyContent: 'center' }}>
                <Svg width={24} height={24} viewBox="0 0 24 24"><Path d="M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15 9.5h.01" stroke={C.fg} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" /></Svg>
              </View>
              <K size={10}>{tr('gallery')}</K>
            </Press>
            <Press accessibilityRole="button" accessibilityLabel="Scan food or label" disabled={busy || !camOk} onPress={snap}
              style={{ width: 76, height: 76, borderRadius: 38, borderWidth: 4, borderColor: C.accent, alignItems: 'center', justifyContent: 'center', opacity: busy || !camOk ? 0.45 : 1 }}>
              <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: C.accent }} />
            </Press>
            <Press accessibilityRole="button" accessibilityLabel="Type a barcode or search a dish" onPress={() => setMode('type')} style={{ alignItems: 'center', gap: 6, width: 80 }}>
              <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: C.track, alignItems: 'center', justifyContent: 'center' }}>
                <Svg width={24} height={24} viewBox="0 0 24 24"><Path d="M4 7h16M4 12h10M4 17h6" stroke={C.fg} strokeWidth={2} strokeLinecap="round" fill="none" /></Svg>
              </View>
              <K size={10}>{tr('type')}</K>
            </Press>
          </View>
        )}
        {mode === 'type' && (
          <>
            <K>Type a barcode number</K>
            <Field label="Barcode number" value={manual} onChangeText={setManual} keyboardType="number-pad" mono />
            <Button title="Look up" onPress={() => scan(manual)} busy={busy} disabled={manual.length < 8} />
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <Button kind="tonal" title="Search a dish" onPress={() => setMode('search')} style={{ flex: 1, height: 46 }} />
              <Button kind="tonal" title="Back to camera" onPress={() => { setMode('scan'); setErr(null); lock.current = false; }} style={{ flex: 1, height: 46 }} />
            </View>
          </>
        )}
        {mode === 'search' && (
          <>
            <Field label="Dish name (masala dosa, dal, poha)" value={query} onChangeText={setQuery} autoCapitalize="none" onSubmitEditing={lookup} returnKeyType="search" />
            <Button title="Search" busy={busy} disabled={!query.trim()} onPress={lookup} />
            {hits.map((h, i) => (
              <FadeIn key={h.slug} delay={i * 40}>
                <Press accessibilityRole="button" onPress={() => pick(h.slug)} style={{ minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                  <View style={{ flex: 1 }}><Text style={{ fontFamily: F.bodyBold, fontSize: 16, color: C.fg }}>{h.name}</Text><Text style={s.muted}>{h.region} · {h.serving.label}</Text></View>
                  <K color={C.accent}>Details</K>
                </Press>
              </FadeIn>
            ))}
            <Button kind="tonal" title="Back to camera" onPress={() => { setMode('scan'); setErr(null); lock.current = false; }} style={{ height: 46 }} />
          </>
        )}
      </SheetIn>
    </KeyboardAvoidingView>
  );
}
