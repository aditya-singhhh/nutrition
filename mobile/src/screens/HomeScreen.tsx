import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import { api } from '../api';
import { Bar, Card, ErrorText, s } from '../components/ui';
import { C } from '../theme';

export default function HomeScreen({ refreshKey }: { refreshKey: number }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try { setD(await api.today()); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  const t = d?.targets;
  const v = d?.totals;
  return (
    <ScrollView style={{ backgroundColor: C.bg }} contentContainerStyle={{ padding: 16, gap: 12, paddingTop: 48 }}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={load} />}>
      <Text style={s.h1}>Today</Text>
      <ErrorText>{err}</ErrorText>
      {d && (t?.available ? (
        <Card>
          <Bar label="Calories" value={v.energy_kcal} max={t.energy_kcal} unit="kcal" />
          <Bar label="Protein" value={v.protein_g} max={t.protein_g} unit="g" />
          <Bar label="Fibre" value={v.fiber_g} max={t.fiber_g} unit="g" />
          <Bar label="Sugar" value={v.sugar_g} max={t.sugar_g_max} unit="g" limit />
          <Bar label="Sodium" value={v.sodium_mg} max={t.sodium_mg_max} unit="mg" limit />
          {d.limits_exceeded?.map((e: any) => (
            <Text key={e.nutrient} style={{ color: C.bad, fontSize: 13 }}>Above the suggested {e.nutrient} limit today.</Text>
          ))}
        </Card>
      ) : (
        <Card tone="warn">
          <Text style={s.body}>
            Add your age, sex, height, weight and activity in Profile to get daily targets.
            So far today: {Math.round(v.energy_kcal)} kcal, {Math.round(v.protein_g)} g protein.
          </Text>
        </Card>
      ))}
      {d && d.incomplete_nutrients?.length > 0 && (
        <Text style={s.muted}>Some foods have missing data, so totals may be lower than actual.</Text>
      )}
      <Text style={s.h2}>Meals</Text>
      {d?.meals?.length === 0 && <Text style={s.muted}>Nothing logged yet. Scan a food or search for a dish.</Text>}
      {d?.meals?.map((m: any) => (
        <Card key={m.id}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={s.h2}>{m.meal_type}</Text>
            <Text style={s.muted}>{Math.round(m.energy_kcal)} kcal</Text>
          </View>
          <Text style={s.body}>{m.items.map((i: any) => `${i.name} (${Math.round(i.grams)} g)`).join(', ')}</Text>
        </Card>
      ))}
      <Text style={s.muted}>Nutrition guidance only, not medical advice.</Text>
    </ScrollView>
  );
}
