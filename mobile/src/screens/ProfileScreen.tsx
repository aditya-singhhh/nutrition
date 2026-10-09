import * as Haptics from 'expo-haptics';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Switch, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { FadeIn, FillBar, Press, SheetIn } from '../anim';
import { api, getBaseUrl, request, setToken } from '../api';
import Screen from '../components/Screen';
import { Button, Card, Chip, Display, ErrorText, Field, K, s } from '../components/ui';
import { C, F } from '../theme';

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

export default function ProfileScreen({ onLogout, onSaved }: { onLogout: () => void; onSaved: () => void }) {
  const { bottom } = useSafeAreaInsets();
  const [f, setF] = useState<Form>(EMPTY);
  const [base, setBase] = useState<Form>(EMPTY);
  const [email, setEmail] = useState('');
  const [targets, setTargets] = useState<any>(null);
  const [loaded, setLoaded] = useState(false);
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
      setF(form); setBase(form); setEmail(me.email ?? '');
      setTargets(await request('GET', '/users/me/targets'));
      setLoaded(true);
    } catch (e: any) { setErr(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const errors = useMemo(() => validate(f), [f]);
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

  const initial = (f.name.trim() || email || '?').charAt(0).toUpperCase();
  const showSaveBar = dirty || saved;
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <Screen>
        <FadeIn><Display size={52}>Profile</Display></FadeIn>
        <ErrorText>{err}</ErrorText>

        <FadeIn delay={60}>
          <Card tone="ink" style={{ gap: 14 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
              <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: C.gold, alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ fontFamily: F.display, fontSize: 28, color: C.ink }}>{initial}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text numberOfLines={1} style={{ fontFamily: F.display, fontSize: 24, color: '#fff', textTransform: 'uppercase' }}>{f.name.trim() || 'Your name'}</Text>
                <Text numberOfLines={1} style={{ fontFamily: F.body, fontSize: 13, color: C.onInk }}>{email}</Text>
              </View>
              <K color={C.gold} size={16}>{pct}%</K>
            </View>
            <FillBar pct={pct} color={C.gold} track="#2B3B33" height={8} />
            <Text style={{ fontFamily: F.body, fontSize: 13, color: C.onInk }}>
              {pct === 100 ? 'Profile complete. Your suggestions and limits are fully personalised.' : `Add ${missing.slice(0, 3).join(', ')}${missing.length > 3 ? ' and more' : ''} to personalise your daily targets and food advice.`}
            </Text>
          </Card>
        </FadeIn>

        {loaded && targets?.available && (
          <FadeIn delay={100}>
            <Card>
              <K>Your daily targets</K>
              <Text style={{ fontFamily: F.display, fontSize: 44, color: C.fg }}>{Number(targets.energy_kcal).toLocaleString('en-IN')} <Text style={{ fontSize: 15, color: C.muted }}>KCAL</Text></Text>
              <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
                {[['Protein', `${targets.protein_g} g`], ['Carbs', `${targets.carbs_g} g`], ['Fat', `${targets.fat_g} g`], ['Fibre', `${targets.fiber_g} g`]].map(([l, v]) => (
                  <View key={l} style={{ backgroundColor: C.bg, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8 }}><K size={9}>{l}</K><Text style={[s.strong, { fontVariant: ['tabular-nums'] }]}>{v}</Text></View>
                ))}
              </View>
              <Text style={s.muted}>Limits per day: sugar {targets.sugar_g_max} g · sodium {targets.sodium_mg_max} mg · saturated fat {targets.sat_fat_g_max} g. Starting estimates, not a prescription.</Text>
              {targets.safety_floor_applied && <Text style={s.muted}>A minimum safe calorie level was applied.</Text>}
            </Card>
          </FadeIn>
        )}
        {loaded && targets && !targets.available && targets.message && <Card tone="warn"><Text style={s.body}>{targets.message}</Text></Card>}
        {loaded && targets && !targets.available && targets.reason === 'incomplete_profile' && (
          <Card tone="warn"><Text style={s.body}>To calculate targets we still need: {targets.missing_fields?.map((m: string) => pretty(m).replace(' cm', '').replace(' kg', '')).join(', ')}.</Text></Card>
        )}

        <Section title="About you" delay={140}>
          <Field label="Your name" value={f.name} onChangeText={(t) => set('name', t)} maxLength={60} autoCapitalize="words" />
          <Field label="Age" value={f.age} onChangeText={(t) => set('age', t)} keyboardType="number-pad" maxLength={3} />
          <Err t={errors.age} />
          {num(f.age) !== null && (num(f.age) as number) < 18 && <Text style={s.muted}>Under 18: we show food information, but daily targets for young people should come from a paediatrician or dietitian.</Text>}
          <View style={{ gap: 8 }}><K>Sex (used for calorie estimates)</K><Chips opts={SEX} val={f.sex} set={(k) => set('sex', k)} /></View>
          {f.sex !== 'male' && f.sex !== null && (
            <View style={{ gap: 8 }}>
              <K>Pregnancy or breastfeeding</K>
              <Chips opts={[{ key: 'none', label: 'Neither' }, { key: 'pregnant', label: 'Pregnant' }, { key: 'breastfeeding', label: 'Breastfeeding' }]} val={f.lifeStage} set={(k) => set('lifeStage', k)} />
              {f.lifeStage !== 'none' && <Text style={s.muted}>Your needs change a lot right now, so we won't calculate calorie targets. Please follow your doctor's or dietitian's plan. You can still scan foods and check allergens.</Text>}
            </View>
          )}
        </Section>

        <Section title="Body" hint="Used for your calorie and protein targets." delay={180}>
          <Field label="Height (cm)" value={f.height} onChangeText={(t) => set('height', t)} keyboardType="decimal-pad" maxLength={5} />
          <Err t={errors.height} />
          <Field label="Weight (kg)" value={f.weight} onChangeText={(t) => set('weight', t)} keyboardType="decimal-pad" maxLength={6} />
          <Err t={errors.weight} />
          {bmi && (
            <View style={{ gap: 8, backgroundColor: C.bg, borderRadius: 14, padding: 14 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <K>BMI</K><Text style={{ fontFamily: F.display, fontSize: 28, color: C.fg }}>{bmi.v}</Text>
              </View>
              <FillBar pct={bmi.pct} color={bmi.tone} track={C.track} height={6} />
              <Text style={s.muted}>{bmi.label} (Asian-Indian cut-offs). BMI is a rough guide only and doesn't account for muscle or body shape.</Text>
            </View>
          )}
        </Section>

        <Section title="Lifestyle and goal" delay={220}>
          <View style={{ gap: 8 }}><K>How active are you?</K><Rows opts={ACTIVITY} val={f.activity} set={(k) => set('activity', k)} /></View>
          <View style={{ gap: 8 }}><K>Your goal</K><Rows opts={GOAL} val={f.goal} set={(k) => set('goal', k)} /></View>
          <Field label="Target weight (kg, optional)" value={f.target} onChangeText={(t) => set('target', t)} keyboardType="decimal-pad" maxLength={6} />
          <Err t={errors.target} />
          {goalHint && <Text style={[s.muted, { color: C.warn }]}>{goalHint}</Text>}
        </Section>

        <Section title="Food preferences" delay={260}>
          <View style={{ gap: 8 }}><K>Diet</K><Chips opts={DIET} val={f.diet} set={(k) => set('diet', k)} /></View>
          <View style={{ gap: 8 }}><K>Cuisine you eat most</K><Chips opts={REGION} val={f.region} set={(k) => set('region', k)} /></View>
        </Section>

        <Section title="Health" hint="We use this to flag foods that may not suit you. It is not a diagnosis." delay={300}>
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
        </Section>

        <Section title="Privacy" hint="Your scans are saved to your account so we can show your history and improve accuracy. Delete your account and they go too." delay={330}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <View style={{ flex: 1, gap: 3 }}>
              <Text style={{ fontFamily: F.bodyBold, fontSize: 15, color: C.fg }}>Help improve food recognition</Text>
              <Text style={s.muted}>Also keep the photos you scan, so we can train and test the app on real Indian food. Off by default. Turn it off any time; photos already saved are removed when you delete your account.</Text>
            </View>
            <Switch value={f.share} onValueChange={(v) => set('share', v)} trackColor={{ true: C.accent }} thumbColor="#fff" accessibilityLabel="Help improve food recognition" />
          </View>
        </Section>

        <Section title="Account" delay={340}>
          <View style={{ gap: 3 }}><K size={10}>Signed in as</K><Text style={s.body}>{email}</Text></View>
          <View style={{ gap: 3 }}><K size={10}>Server</K><Text style={{ fontFamily: F.mono, fontSize: 12, color: C.fg }}>{getBaseUrl()}</Text></View>
          <Button kind="tonal" title="Log out" onPress={async () => { await setToken(null); onLogout(); }} />
          <Press accessibilityRole="button" onPress={confirmDelete} style={{ height: 44, alignItems: 'center', justifyContent: 'center' }}><K color={C.bad}>Delete my account</K></Press>
        </Section>
        <Text style={s.muted}>Nutrition guidance only, not medical advice.</Text>
      </Screen>

      {showSaveBar && (
        <SheetIn style={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12, backgroundColor: C.bg, borderTopWidth: 1, borderColor: C.line, gap: 8 }}>
          {hasErrors && <Text style={{ color: C.bad, fontFamily: F.bodyMed, fontSize: 13 }}>Fix the highlighted fields to save.</Text>}
          <Button title={saved && !dirty ? 'Saved ✓' : 'Save profile'} onPress={save} busy={busy} disabled={hasErrors || (!dirty && saved)} />
        </SheetIn>
      )}
      <View style={{ height: 0, marginBottom: bottom ? 0 : 0 }} />
    </View>
  );
}
