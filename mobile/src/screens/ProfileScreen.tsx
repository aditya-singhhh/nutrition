import React, { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { FadeIn } from '../anim';
import { api, getBaseUrl, request, setToken } from '../api';
import Screen from '../components/Screen';
import { Button, Card, Chip, Display, ErrorText, Field, K, s } from '../components/ui';
import { C, F } from '../theme';

const SEX = ['male', 'female', 'other'];
const ACTIVITY = ['sedentary', 'light', 'moderate', 'active'];
const GOAL = ['maintain', 'lose', 'gain'];
const DIET = ['vegan', 'vegetarian', 'eggetarian', 'non_vegetarian'];
const CONDITIONS = ['diabetes', 'hypertension', 'high_cholesterol', 'hyperuricemia', 'fatty_liver', 'iron_deficiency',
  'b12_deficiency', 'vitamin_d_deficiency'];
const RULES_FOR = ['diabetes', 'hypertension', 'high_cholesterol'];
const ALLERGENS = ['milk', 'gluten', 'soy', 'peanut', 'tree_nuts', 'egg', 'fish', 'shellfish', 'sesame', 'mustard', 'sulphites'];

const pretty = (x: string) => x.replace(/_/g, ' ');
const toggle = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

export default function ProfileScreen({ onLogout, onSaved }: { onLogout: () => void; onSaved: () => void }) {
  const [age, setAge] = useState('');
  const [height, setHeight] = useState('');
  const [weight, setWeight] = useState('');
  const [sex, setSex] = useState<string | null>(null);
  const [activity, setActivity] = useState<string | null>(null);
  const [goal, setGoal] = useState<string | null>(null);
  const [diet, setDiet] = useState<string | null>(null);
  const [conditions, setConditions] = useState<string[]>([]);
  const [allergies, setAllergies] = useState<string[]>([]);
  const [targets, setTargets] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const me: any = await api.me();
        const p = me.profile ?? {};
        setAge(p.age ? String(p.age) : '');
        setHeight(p.height_cm ? String(p.height_cm) : '');
        setWeight(p.weight_kg ? String(p.weight_kg) : '');
        setSex(p.sex ?? null); setActivity(p.activity_level ?? null); setGoal(p.goal ?? null); setDiet(p.diet_preference ?? null);
        setConditions(me.conditions ?? []); setAllergies(me.allergies ?? []);
        setTargets(await request('GET', '/users/me/targets'));
      } catch (e: any) { setErr(e.message); }
    })();
  }, []);

  async function save() {
    setBusy(true); setErr(null); setMsg(null);
    try {
      await api.updateProfile({
        age: age ? Number(age) : null, height_cm: height ? Number(height) : null, weight_kg: weight ? Number(weight) : null,
        sex, activity_level: activity, goal, diet_preference: diet, conditions, allergies,
      });
      setTargets(await request('GET', '/users/me/targets'));
      setMsg('Saved.');
      onSaved();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  const group = (label: string, opts: string[], val: string | null, set: (v: string) => void) => (
    <View style={{ gap: 6 }}>
      <K>{label}</K>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {opts.map((o) => <Chip key={o} label={pretty(o)} on={val === o} onPress={() => set(o)} />)}
      </View>
    </View>
  );

  return (
    <Screen>
      <FadeIn><Display size={52}>Profile</Display></FadeIn>
      <ErrorText>{err}</ErrorText>
      <Field label="Age" value={age} onChangeText={setAge} keyboardType="number-pad" />
      <Field label="Height (cm)" value={height} onChangeText={setHeight} keyboardType="decimal-pad" />
      <Field label="Weight (kg)" value={weight} onChangeText={setWeight} keyboardType="decimal-pad" />
      {group('Sex', SEX, sex, setSex)}
      {group('Activity', ACTIVITY, activity, setActivity)}
      {group('Goal', GOAL, goal, setGoal)}
      {group('Diet', DIET, diet, setDiet)}
      <View style={{ gap: 6 }}>
        <K>Health conditions</K>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {CONDITIONS.map((c) => <Chip key={c} label={pretty(c)} on={conditions.includes(c)} onPress={() => setConditions(toggle(conditions, c))} />)}
        </View>
        {conditions.some((c) => !RULES_FOR.includes(c)) && (
          <Text style={s.muted}>Detailed food rules exist only for diabetes, hypertension and high cholesterol so far. For the others, please follow your doctor's or dietitian's plan.</Text>
        )}
      </View>
      <View style={{ gap: 6 }}>
        <K>Allergies</K>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {ALLERGENS.map((a) => <Chip key={a} label={pretty(a)} on={allergies.includes(a)} onPress={() => setAllergies(toggle(allergies, a))} />)}
        </View>
      </View>
      {msg && <Text style={{ color: C.accent, fontFamily: F.bodyBold }}>{msg}</Text>}
      <Button title="Save profile" onPress={save} busy={busy} />

      {targets?.available && (
        <FadeIn><Card tone="ink">
          <K color={C.onInk}>Your daily targets</K>
          <Text style={{ fontFamily: F.display, fontSize: 48, color: '#fff' }}>{Number(targets.energy_kcal).toLocaleString('en-IN')} <Text style={{ fontSize: 16, color: C.onInk }}>KCAL</Text></Text>
          <Text style={[s.body, { color: '#fff' }]}>{targets.protein_g} g protein · {targets.fiber_g} g fibre</Text>
          <Text style={[s.muted, { color: C.onInk }]}>Limits: sugar {targets.sugar_g_max} g, sodium {targets.sodium_mg_max} mg. Starting estimates, not a prescription.</Text>
          {targets.safety_floor_applied && <Text style={[s.muted, { color: C.onInk }]}>A minimum safe calorie level was applied.</Text>}
        </Card></FadeIn>
      )}
      {targets && !targets.available && targets.reason === 'paediatric_review_required' && (
        <Card tone="warn"><Text style={s.body}>{targets.message}</Text></Card>
      )}

      <Text style={[s.muted, { fontFamily: F.mono, fontSize: 12 }]}>Server: {getBaseUrl()}</Text>
      <Button kind="tonal" title="Log out" onPress={async () => { await setToken(null); onLogout(); }} />
    </Screen>
  );
}
