import * as Haptics from 'expo-haptics';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, KeyboardAvoidingView, Modal, Platform, ScrollView, Share, Switch, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { FadeIn, FillBar, Press, SheetIn } from '../anim';
import { api, getBaseUrl, request, setToken } from '../api';
import Screen from '../components/Screen';
import { Button, Card, Chip, Display, ErrorText, Field, K, LangToggle, Segmented, s } from '../components/ui';
import { useT } from '../i18n';
import { C, F } from '../theme';
import ReviewScreen from './ReviewScreen';

type Opt = { key: string; label: string; desc?: string };
const SEX: Opt[] = [{ key: 'male', label: 'Male' }, { key: 'female', label: 'Female' }, { key: 'other', label: 'Other' }];
const ACTIVITY: Opt[] = [
  { key: 'sedentary', label: 'Mostly sitting', desc: 'Desk job, little or no exercise' },
  { key: 'light', label: 'Lightly active', desc: 'Walks or exercise 1–3 days a week' },
  { key: 'moderate', label: 'Moderately active', desc: 'Exercise 3–5 days a week' },
  { key: 'active', label: 'Very active', desc: 'Hard exercise most days or a physical job' },
];
const GOAL: Opt[] = [
  { key: 'lose', label: 'Lose weight', desc: 'Gradually, with a small calorie deficit' },
  { key: 'maintain', label: 'Maintain weight', desc: 'Stay where I am' },
  { key: 'gain', label: 'Gain weight', desc: 'Build weight or muscle with a small surplus' },
];
const DIET: Opt[] = [{ key: 'vegan', label: 'Vegan' }, { key: 'vegetarian', label: 'Vegetarian' }, { key: 'eggetarian', label: 'Eggetarian' }, { key: 'non_vegetarian', label: 'Non-veg' }];
const REGION: Opt[] = [{ key: 'north_indian', label: 'North Indian' }, { key: 'south_indian', label: 'South Indian' }, { key: 'east_indian', label: 'East Indian' },
  { key: 'west_indian', label: 'West Indian' }, { key: 'central_indian', label: 'Central Indian' }, { key: 'other', label: 'Other' }];
const CONDITIONS = ['diabetes', 'hypertension', 'high_cholesterol', 'hyperuricemia', 'fatty_liver', 'iron_deficiency', 'b12_deficiency', 'vitamin_d_deficiency'];
const RULES_FOR = ['diabetes', 'hypertension', 'high_cholesterol'];
const ALLERGENS = ['milk', 'gluten', 'soy', 'peanut', 'tree_nuts', 'egg', 'fish', 'shellfish', 'sesame', 'mustard', 'sulphites'];
const pretty = (x: string) => x.replace(/_/g, ' ');
const toggle = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
const num = (t: string) => { const n = parseFloat(t.replace(',', '.')); return Number.isFinite(n) ? n : null; };

type Form = { name: string; age: string; sex: string | null; height: string; weight: string; target: string; activity: string | null; goal: string | null;
  diet: string | null; region: string | null; lifeStage: string; conditions: string[]; allergies: string[]; share: boolean };
const EMPTY: Form = { name: '', age: '', sex: null, height: '', weight: '', target: '', activity: null, goal: null, diet: null, region: null, lifeStage: 'none', conditions: [], allergies: [], share: false };

function bmiInfo(h: number | null, w: number | null) {
  if (!h || !w || h < 100) return null;
  const v = w / ((h / 100) ** 2);
  // WHO Asia-Pacific cut-offs, commonly used for Indian adults
  const [label, tone] = v < 18.5 ? ['Below the healthy range', C.gold] : v < 23 ? ['In the healthy range', C.accent] : v < 27.5 ? ['Above the healthy range', C.gold] : ['Well above the healthy range', '#C8402F'];
  return { v: Math.round(v * 10) / 10, label, tone, pct: Math.max(0, Math.min(100, ((v - 14) / (36 - 14)) * 100)) };
}

function validate(f: Form): Record<string, string> {
  const e: Record<string, string> = {};
  const chk = (key: string, text: string, lo: number, hi: number, label: string) => {
    if (!text.trim()) return;
    const n = num(text);
    if (n === null || n < lo || n > hi) e[key] = `${label} should be between ${lo} and ${hi}`;
  };
  chk('age', f.age, 1, 120, 'Age'); chk('height', f.height, 50, 250, 'Height'); chk('weight', f.weight, 10, 400, 'Weight'); chk('target', f.target, 10, 400, 'Target');
  return e;
}

function Section({ title, hint, children, delay = 0 }: { title: string; hint?: string; children: React.ReactNode; delay?: number }) {
  return (
    <FadeIn delay={delay}>
      <Card style={{ gap: 16 }}>
        <View style={{ gap: 4 }}><K color={C.fg} size={12}>{title}</K>{hint ? <Text style={s.muted}>{hint}</Text> : null}</View>
        {children}
      </Card>
    </FadeIn>
  );
}
const Chips = ({ opts, val, set }: { opts: Opt[]; val: string | null; set: (k: string) => void }) => (
  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>{opts.map((o) => <Chip key={o.key} label={o.label} on={val === o.key} onPress={() => set(o.key)} />)}</View>
);
const Rows = ({ opts, val, set }: { opts: Opt[]; val: string | null; set: (k: string) => void }) => (
  <View style={{ gap: 8 }}>
    {opts.map((o) => {
      const on = val === o.key;
      return (
        <Press key={o.key} accessibilityRole="radio" accessibilityState={{ selected: on }} onPress={() => { Haptics.selectionAsync().catch(() => {}); set(o.key); }}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 14, borderWidth: on ? 2 : 1, borderColor: on ? C.accent : C.line, backgroundColor: on ? C.accentSoft : C.surface }}>
          <View style={{ width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: on ? C.accent : '#9DB0A5', alignItems: 'center', justifyContent: 'center' }}>
            {on && <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: C.accent }} />}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontFamily: F.bodyBold, fontSize: 15, color: C.fg }}>{o.label}</Text>
            {o.desc ? <Text style={s.muted}>{o.desc}</Text> : null}
          </View>
        </Press>
      );
    })}
  </View>
);
const Err = ({ t }: { t?: string }) => (t ? <Text style={{ color: C.bad, fontFamily: F.bodyMed, fontSize: 13, marginTop: -8 }}>{t}</Text> : null);


/* ---- settings-style list pieces ---- */
const ICONS: Record<string, string> = {
  user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c1-4 4-6 8-6s7 2 8 6', ruler: 'M3 17L17 3l4 4L7 21zM8 10l2 2M11 7l2 2M5 15l2 2',
  target: 'M12 21a9 9 0 100-18 9 9 0 000 18zM12 16a4 4 0 100-8 4 4 0 000 8zM12 12h.01', bowl: 'M3 11h18a8 8 0 01-8 8h-2a8 8 0 01-8-8zM8 7c0-2 2-2 2-4M13 7c0-2 2-2 2-4',
  heart: 'M12 20s-8-5-8-11a4.5 4.5 0 018-2.8A4.5 4.5 0 0120 9c0 6-8 11-8 11z', share: 'M12 15V3M7 8l5-5 5 5M5 13v6a2 2 0 002 2h10a2 2 0 002-2v-6',
  check: 'M5 12.5l4.5 4.5L19 7.5', out: 'M15 4h3a2 2 0 012 2v12a2 2 0 01-2 2h-3M10 8l-4 4 4 4M6 12h10', trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
};
function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 8 }}>
      <Text style={{ fontFamily: F.bodyBold, fontSize: 13, color: C.muted, marginLeft: 6 }}>{title}</Text>
      <View style={{ backgroundColor: C.surface, borderRadius: 18, borderWidth: 1, borderColor: C.line, overflow: 'hidden' }}>{children}</View>
    </View>
  );
}
function ListRow({ icon, title, value, onPress, last, danger }: { icon: string; title: string; value?: string; onPress: () => void; last?: boolean; danger?: boolean }) {
  const col = danger ? C.bad : C.accent;
  return (
    <Press accessibilityRole="button" accessibilityLabel={title} onPress={() => { Haptics.selectionAsync().catch(() => {}); onPress(); }}
      style={{ minHeight: 60, flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: last ? 0 : 1, borderColor: C.line }}>
      <View style={{ width: 36, height: 36, borderRadius: 11, backgroundColor: danger ? C.badSoft : C.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
        <Svg width={19} height={19} viewBox="0 0 24 24"><Path d={ICONS[icon]} stroke={col} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" /></Svg>
      </View>
      <View style={{ flex: 1, gap: 1 }}>
        <Text style={{ fontFamily: F.bodyBold, fontSize: 15, color: danger ? C.bad : C.fg }}>{title}</Text>
        {value ? <Text numberOfLines={1} style={s.muted}>{value}</Text> : null}
      </View>
      {!danger && <Svg width={16} height={16} viewBox="0 0 24 24"><Path d="M9 5l7 7-7 7" stroke="#98A39C" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" fill="none" /></Svg>}
    </Press>
  );
}
function EditSheet({ visible, title, onClose, children }: { visible: boolean; title: string; onClose: () => void; children: React.ReactNode }) {
  const { bottom } = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(14,26,21,.45)' }}>
        <Press accessibilityLabel="Close" onPress={onClose} style={{ flex: 1 }}><View style={{ flex: 1 }} /></Press>
        <View style={{ backgroundColor: C.bg, borderTopLeftRadius: 28, borderTopRightRadius: 28, maxHeight: '88%', paddingTop: 10 }}>
          <View style={{ alignSelf: 'center', width: 38, height: 4, borderRadius: 2, backgroundColor: '#C9CFC4' }} />
          <Text style={{ fontFamily: F.display, fontSize: 22, color: C.fg, paddingHorizontal: 20, paddingTop: 12, paddingBottom: 4 }}>{title}</Text>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingBottom: 12, gap: 18 }}>{children}</ScrollView>
          <View style={{ padding: 16, paddingBottom: Math.max(bottom, 12) + 4 }}><Button title="Done" onPress={onClose} /></View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

export default function ProfileScreen({ onLogout, onSaved }: { onLogout: () => void; onSaved: () => void }) {
  const { t: tr } = useT();
  const { bottom } = useSafeAreaInsets();
  const [f, setF] = useState<Form>(EMPTY);
  const [base, setBase] = useState<Form>(EMPTY);
  const [email, setEmail] = useState('');
  const [targets, setTargets] = useState<any>(null);
  const [loaded, setLoaded] = useState(false);
  const [admin, setAdmin] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => { setF((x) => ({ ...x, [k]: v })); setSaved(false); };

  const load = useCallback(async () => {
    try {
      const me: any = await api.me();
      const p = me.profile ?? {};
      const form: Form = {
        name: p.display_name ?? '', age: p.age ? String(p.age) : '', sex: p.sex ?? null, height: p.height_cm ? String(p.height_cm) : '',
        weight: p.weight_kg ? String(p.weight_kg) : '', target: p.target_weight_kg ? String(p.target_weight_kg) : '', activity: p.activity_level ?? null,
        goal: p.goal ?? null, diet: p.diet_preference ?? null, region: p.region ?? null, lifeStage: p.life_stage ?? 'none',
        conditions: me.conditions ?? [], allergies: me.allergies ?? [], share: !!p.training_opt_in };
      setF(form); setBase(form); setEmail(me.email ?? ''); setAdmin(!!me.is_admin);
      setTargets(await request('GET', '/users/me/targets'));
      setLoaded(true);
    } catch (e: any) { setErr(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const errors = useMemo(() => validate(f), [f]);
  const [sheet, setSheet] = useState<null | 'about' | 'body' | 'goal' | 'food' | 'health'>(null);
  const dirty = useMemo(() => JSON.stringify(f) !== JSON.stringify(base), [f, base]);
  const hasErrors = Object.keys(errors).length > 0;
  const bmi = f.lifeStage === 'none' && (num(f.age) ?? 18) >= 18 ? bmiInfo(num(f.height), num(f.weight)) : null;

  const checks: [string, boolean][] = [['Name', !!f.name.trim()], ['Age', !!f.age], ['Sex', !!f.sex], ['Height', !!f.height], ['Weight', !!f.weight],
    ['Activity', !!f.activity], ['Goal', !!f.goal], ['Diet', !!f.diet], ['Cuisine', !!f.region]];
  const done = checks.filter(([, ok]) => ok).length;
  const pct = Math.round((done / checks.length) * 100);
  const missing = checks.filter(([, ok]) => !ok).map(([n]) => n);
  const goalHint = (() => {
    const w = num(f.weight), t = num(f.target);
    if (!w || !t || !f.goal) return null;
    if (f.goal === 'lose' && t >= w) return 'Your target is not below your current weight. Check your goal or target.';
    if (f.goal === 'gain' && t <= w) return 'Your target is not above your current weight. Check your goal or target.';
    if (f.goal === 'maintain' && Math.abs(t - w) > 2) return 'Your target differs from your current weight. Is your goal to lose or gain?';
    return null;
  })();

  async function save() {
    if (hasErrors) return;
    setBusy(true); setErr(null);
    try {
      await api.updateProfile({
        display_name: f.name.trim() || null, age: num(f.age), height_cm: num(f.height), weight_kg: num(f.weight), target_weight_kg: num(f.target),
        sex: f.sex, activity_level: f.activity, goal: f.goal, diet_preference: f.diet, region: f.region, life_stage: f.lifeStage,
        conditions: f.conditions, allergies: f.allergies, training_opt_in: f.share });
      setBase(f); setSaved(true);
      setTargets(await request('GET', '/users/me/targets'));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      onSaved();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  function confirmDelete() {
    Alert.alert('Delete your account?', 'This permanently removes your profile, meals, chats and scan history. It cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete everything', style: 'destructive', onPress: async () => {
        try { await api.deleteAccount(); await setToken(null); onLogout(); } catch (e: any) { setErr(e.message); } } },
    ]);
  }

  async function shareReport() {
    try { const r: any = await api.report(7); await Share.share({ message: r.text }); } catch (e: any) { setErr(e.message); }
  }
  if (reviewing) return <ReviewScreen onClose={() => setReviewing(false)} />;
  const initial = (f.name.trim() || email || '?').charAt(0).toUpperCase();
  const showSaveBar = dirty || saved;
  const label = (opts: Opt[], k: string | null) => opts.find((o) => o.key === k)?.label;
  const join = (...x: (string | null | undefined | false)[]) => x.filter(Boolean).join(' · ');
  const summary = {
    about: join(f.name.trim(), f.age && `${f.age} yrs`, label(SEX, f.sex)) || 'Add your details',
    body: join(f.height && `${f.height} cm`, f.weight && `${f.weight} kg`, bmi && `BMI ${bmi.v}`) || 'Add height and weight',
    goal: join(label(GOAL, f.goal), label(ACTIVITY, f.activity)) || 'Choose your goal',
    food: join(label(DIET, f.diet), label(REGION, f.region)) || 'Choose your diet',
    health: join(f.conditions.length ? `${f.conditions.length} condition${f.conditions.length > 1 ? 's' : ''}` : 'No conditions', f.allergies.length ? `${f.allergies.length} allerg${f.allergies.length > 1 ? 'ies' : 'y'}` : 'No allergies'),
  };
  const body = (label: string, value?: string | null) => (
    <View style={{ flex: 1, alignItems: 'center', gap: 2 }}><Text style={{ fontFamily: F.display, fontSize: 20, color: C.fg }}>{value || '–'}</Text><Text style={s.muted}>{label}</Text></View>
  );

  if (reviewing) return <ReviewScreen onClose={() => setReviewing(false)} />;

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <Screen contentContainerStyle={{ gap: 18, paddingBottom: showSaveBar ? 110 : 28 }}>
        <FadeIn>
          <View style={{ alignItems: 'center', gap: 6, paddingTop: 4 }}>
            <View style={{ width: 84, height: 84, borderRadius: 42, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center' }}>
              <Text style={{ fontFamily: F.display, fontSize: 38, color: '#fff' }}>{initial}</Text>
            </View>
            <Text numberOfLines={1} style={{ fontFamily: F.display, fontSize: 24, color: C.fg, marginTop: 4 }}>{f.name.trim() || 'Your name'}</Text>
            <Text numberOfLines={1} style={s.muted}>{email}</Text>
            {pct < 100 ? (
              <Press accessibilityRole="button" onPress={() => setSheet('about')} style={{ marginTop: 6, flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: C.warnSoft, paddingHorizontal: 14, paddingVertical: 9, borderRadius: 20 }}>
                <View style={{ width: 70 }}><FillBar pct={pct} color={C.gold} track="#EBDDA8" height={6} /></View>
                <Text style={{ fontFamily: F.bodyBold, fontSize: 12, color: C.warn }}>{pct}% · {missing.slice(0, 2).join(', ')}{missing.length > 2 ? '…' : ''}</Text>
              </Press>
            ) : (
              <View style={{ marginTop: 6, backgroundColor: C.accentSoft, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20 }}>
                <Text style={{ fontFamily: F.bodyBold, fontSize: 12, color: C.accentText }}>✓ {tr('profileComplete')}</Text>
              </View>
            )}
          </View>
        </FadeIn>

        {loaded && targets?.available && (
          <FadeIn delay={60}>
            <Card tone="ink" style={{ gap: 12 }}>
              <Text style={{ fontFamily: F.bodyMed, fontSize: 13, color: C.onInk }}>Your daily plan</Text>
              <Text style={{ fontFamily: F.display, fontSize: 40, color: '#fff' }}>{Number(targets.energy_kcal).toLocaleString('en-IN')} <Text style={{ fontSize: 15, color: C.onInk }}>kcal</Text></Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {[['Protein', targets.protein_g], ['Carbs', targets.carbs_g], ['Fat', targets.fat_g], ['Fibre', targets.fiber_g]].map(([l, v]) => (
                  <View key={String(l)} style={{ flex: 1, backgroundColor: 'rgba(255,255,255,.09)', borderRadius: 12, paddingVertical: 8, alignItems: 'center' }}>
                    <Text style={{ fontFamily: F.bodyBold, fontSize: 15, color: '#fff' }}>{v} g</Text>
                    <Text style={{ fontFamily: F.body, fontSize: 11, color: C.onInk }}>{l}</Text>
                  </View>
                ))}
              </View>
              <Text style={{ fontFamily: F.body, fontSize: 12, color: C.onInk }}>Limits: sugar {targets.sugar_g_max} g · salt-sodium {targets.sodium_mg_max} mg · sat fat {targets.sat_fat_g_max} g. Starting estimates.</Text>
            </Card>
          </FadeIn>
        )}
        {loaded && targets && !targets.available && (targets.message || targets.reason === 'incomplete_profile') && (
          <Card tone="warn"><Text style={s.body}>{targets.message ?? `To calculate your plan we still need: ${targets.missing_fields?.map((m: string) => pretty(m).replace(' cm', '').replace(' kg', '')).join(', ')}.`}</Text></Card>
        )}

        <FadeIn delay={100}>
          <Group title="About you">
            <ListRow icon="user" title="Personal" value={summary.about} onPress={() => setSheet('about')} />
            <ListRow icon="ruler" title="Body" value={summary.body} onPress={() => setSheet('body')} />
            <ListRow icon="target" title="Goal and activity" value={summary.goal} onPress={() => setSheet('goal')} last />
          </Group>
        </FadeIn>
        <FadeIn delay={140}>
          <Group title="Food and health">
            <ListRow icon="bowl" title="Food preferences" value={summary.food} onPress={() => setSheet('food')} />
            <ListRow icon="heart" title="Conditions and allergies" value={summary.health} onPress={() => setSheet('health')} last />
          </Group>
        </FadeIn>
        <FadeIn delay={180}>
          <Group title="App">
            <View style={{ minHeight: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, borderBottomWidth: 1, borderColor: C.line }}>
              <Text style={s.strong}>{tr('language')}</Text><LangToggle />
            </View>
            <View style={{ minHeight: 64, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderColor: C.line }}>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={s.strong}>Help improve food recognition</Text>
                <Text style={s.muted}>Also keep photos you scan, to train the app on Indian food. Off by default.</Text>
              </View>
              <Switch value={f.share} onValueChange={(v) => set('share', v)} trackColor={{ true: C.accent }} thumbColor="#fff" accessibilityLabel="Help improve food recognition" />
            </View>
            <ListRow icon="share" title={tr('shareSummary')} onPress={shareReport} last={!admin} />
            {admin && <ListRow icon="check" title="Review products (admin)" onPress={() => setReviewing(true)} last />}
          </Group>
        </FadeIn>
        <FadeIn delay={220}>
          <Group title="Account">
            <ListRow icon="out" title={tr('logOut')} onPress={async () => { await setToken(null); onLogout(); }} />
            <ListRow icon="trash" title={tr('deleteAccount')} danger onPress={confirmDelete} last />
          </Group>
        </FadeIn>
        <ErrorText>{err}</ErrorText>
        <Text style={[s.muted, { textAlign: 'center' }]}>{tr('disclaimer')} · {getBaseUrl().replace('https://', '')}</Text>
      </Screen>

      {showSaveBar && (
        <SheetIn style={{ position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12, backgroundColor: C.bg, borderTopWidth: 1, borderColor: C.line, gap: 8 }}>
          {hasErrors && <Text style={{ color: C.bad, fontFamily: F.bodyMed, fontSize: 13 }}>Fix the highlighted fields to save.</Text>}
          <Button title={saved && !dirty ? tr('saved') : tr('saveProfile')} onPress={save} busy={busy} disabled={hasErrors || (!dirty && saved)} />
        </SheetIn>
      )}

      <EditSheet visible={sheet === 'about'} title="Personal" onClose={() => setSheet(null)}>
        <Field label="Your name" value={f.name} onChangeText={(t) => set('name', t)} maxLength={60} autoCapitalize="words" />
        <Field label="Age" value={f.age} onChangeText={(t) => set('age', t)} keyboardType="number-pad" maxLength={3} />
        <Err t={errors.age} />
        {num(f.age) !== null && (num(f.age) as number) < 18 && <Text style={s.muted}>Under 18: we show food information, but daily targets for young people should come from a paediatrician or dietitian.</Text>}
        <View style={{ gap: 8 }}><K>Sex (used for calorie estimates)</K><Chips opts={SEX} val={f.sex} set={(k) => set('sex', k)} /></View>
        {f.sex !== 'male' && f.sex !== null && (
          <View style={{ gap: 8 }}>
            <K>Pregnancy or breastfeeding</K>
            <Chips opts={[{ key: 'none', label: 'Neither' }, { key: 'pregnant', label: 'Pregnant' }, { key: 'breastfeeding', label: 'Breastfeeding' }]} val={f.lifeStage} set={(k) => set('lifeStage', k)} />
            {f.lifeStage !== 'none' && <Text style={s.muted}>Your needs change a lot right now, so we won't calculate calorie targets. Please follow your doctor's or dietitian's plan.</Text>}
          </View>
        )}
      </EditSheet>

      <EditSheet visible={sheet === 'body'} title="Body" onClose={() => setSheet(null)}>
        <Field label="Height (cm)" value={f.height} onChangeText={(t) => set('height', t)} keyboardType="decimal-pad" maxLength={5} />
        <Err t={errors.height} />
        <Field label="Weight (kg)" value={f.weight} onChangeText={(t) => set('weight', t)} keyboardType="decimal-pad" maxLength={6} />
        <Err t={errors.weight} />
        {bmi && (
          <View style={{ gap: 8, backgroundColor: C.bg, borderRadius: 14, padding: 14 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <K>BMI</K><Text style={{ fontFamily: F.display, fontSize: 26, color: C.fg }}>{bmi.v}</Text>
            </View>
            <FillBar pct={bmi.pct} color={bmi.tone} track={C.track} height={6} />
            <Text style={s.muted}>{bmi.label} (Asian-Indian cut-offs). A rough guide only.</Text>
          </View>
        )}
      </EditSheet>

      <EditSheet visible={sheet === 'goal'} title="Goal and activity" onClose={() => setSheet(null)}>
        <View style={{ gap: 8 }}><K>Your goal</K><Rows opts={GOAL} val={f.goal} set={(k) => set('goal', k)} /></View>
        <View style={{ gap: 8 }}><K>How active are you?</K><Rows opts={ACTIVITY} val={f.activity} set={(k) => set('activity', k)} /></View>
        <Field label="Target weight (kg, optional)" value={f.target} onChangeText={(t) => set('target', t)} keyboardType="decimal-pad" maxLength={6} />
        <Err t={errors.target} />
        {goalHint && <Text style={[s.muted, { color: C.warn }]}>{goalHint}</Text>}
      </EditSheet>

      <EditSheet visible={sheet === 'food'} title="Food preferences" onClose={() => setSheet(null)}>
        <View style={{ gap: 8 }}><K>Diet</K><Chips opts={DIET} val={f.diet} set={(k) => set('diet', k)} /></View>
        <View style={{ gap: 8 }}><K>Cuisine you eat most</K><Chips opts={REGION} val={f.region} set={(k) => set('region', k)} /></View>
      </EditSheet>

      <EditSheet visible={sheet === 'health'} title="Conditions and allergies" onClose={() => setSheet(null)}>
        <Text style={s.muted}>We use this to flag foods that may not suit you. It is not a diagnosis.</Text>
        <View style={{ gap: 8 }}>
          <K>Conditions</K>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {CONDITIONS.map((c) => <Chip key={c} label={pretty(c)} on={f.conditions.includes(c)} onPress={() => set('conditions', toggle(f.conditions, c))} />)}
          </View>
          {f.conditions.some((c) => !RULES_FOR.includes(c)) && <Text style={s.muted}>Detailed food rules exist only for diabetes, hypertension and high cholesterol so far. For the others, please follow your doctor's or dietitian's plan.</Text>}
        </View>
        <View style={{ gap: 8 }}>
          <K>Allergies</K>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {ALLERGENS.map((a) => <Chip key={a} label={pretty(a)} on={f.allergies.includes(a)} onPress={() => set('allergies', toggle(f.allergies, a))} />)}
          </View>
        </View>
      </EditSheet>
    </View>
  );
}
