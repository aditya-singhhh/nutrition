import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, Text, View } from 'react-native';
import { CountUp, FadeIn, FillBar } from '../anim';
import { api } from '../api';
import Screen from '../components/Screen';
import { Button, Card, Display, ErrorText, K, LangToggle, s } from '../components/ui';
import { useT } from '../i18n';
import { C, F } from '../theme';

const Tile = ({ label, value, max, unit, limit }: { label: string; value: number; max: number; unit: string; limit?: boolean }) => {
  const over = limit && value > max;
  return (
    <Card style={{ flex: 1, gap: 8, minWidth: 140 }}>
      <K>{label}</K>
      <Text style={{ fontFamily: F.display, fontSize: 30, color: over ? C.bad : C.fg }}>
        {Math.round(value)}<Text style={{ fontFamily: F.bodyMed, fontSize: 13, color: C.muted }}> / {Math.round(max)} {unit}</Text>
      </Text>
      <FillBar pct={max > 0 ? (value / max) * 100 : 0} color={over ? C.bad : C.accent} track={C.track} height={6} />
    </Card>
  );
};

export default function HomeScreen({ refreshKey, onScan }: { refreshKey: number; onScan: () => void }) {
  const { t: tr } = useT();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setBusy(true); setErr(null);
    try { setD(await api.today()); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  const t = d?.targets; const v = d?.totals;
  const date = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' });
  return (
    <Screen refreshControl={<RefreshControl refreshing={busy} onRefresh={load} colors={[C.accent]} />}>
      <FadeIn style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}><View><K>{date}</K><Display size={44} style={{ marginTop: 6 }}>{tr('today')}</Display></View><LangToggle /></FadeIn>
      <ErrorText>{err}</ErrorText>
      {d && (t?.available ? (
        <>
          <FadeIn delay={80}>
            <Card tone="ink" style={{ gap: 12 }}>
              <K color={C.onInk}>Energy</K>
              <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8 }}>
                <CountUp value={v.energy_kcal} style={{ fontFamily: F.display, fontSize: 56, color: '#fff' }} />
                <Text style={{ fontFamily: F.bodyMed, fontSize: 15, color: C.onInk }}>/ {Math.round(t.energy_kcal).toLocaleString('en-IN')} kcal</Text>
              </View>
              <FillBar pct={(v.energy_kcal / t.energy_kcal) * 100} color={C.gold} track="#2B3B33" height={10} />
            </Card>
          </FadeIn>
          <FadeIn delay={160} style={{ flexDirection: 'row', gap: 12, flexWrap: 'wrap' }}>
            <Tile label="Protein" value={v.protein_g} max={t.protein_g} unit="g" />
            <Tile label="Fibre" value={v.fiber_g} max={t.fiber_g} unit="g" />
          </FadeIn>
          <FadeIn delay={220} style={{ flexDirection: 'row', gap: 12, flexWrap: 'wrap' }}>
            <Tile label="Sugar limit" value={v.sugar_g} max={t.sugar_g_max} unit="g" limit />
            <Tile label="Sodium limit" value={v.sodium_mg} max={t.sodium_mg_max} unit="mg" limit />
          </FadeIn>
          {d.limits_exceeded?.map((e: any) => (
            <Card key={e.nutrient} tone="bad"><Text style={[s.body, { color: C.bad }]}>Above the suggested {e.nutrient} limit today.</Text></Card>
          ))}
        </>
      ) : (
        <FadeIn delay={80}>
          <Card tone="warn">
            <Text style={s.body}>Add your age, sex, height, weight and activity in Profile to get daily targets.</Text>
            <Text style={s.muted}>So far today: {Math.round(v.energy_kcal)} kcal, {Math.round(v.protein_g)} g protein.</Text>
          </Card>
        </FadeIn>
      ))}
      {d?.incomplete_nutrients?.length > 0 && <Text style={s.muted}>Some foods have missing data, so totals may be lower than actual.</Text>}

      <FadeIn delay={280}><K style={{ marginTop: 6 }}>Meals</K></FadeIn>
      {d?.meals?.length === 0 && (
        <FadeIn delay={320}>
          <Card style={{ alignItems: 'flex-start' }}>
            <Text style={s.body}>Nothing logged yet. Scan a barcode, snap your plate, or search a dish.</Text>
            <Button title="Scan food" onPress={onScan} style={{ height: 46 }} />
          </Card>
        </FadeIn>
      )}
      {d?.meals?.map((m: any, i: number) => (
        <FadeIn key={m.id} delay={320 + i * 60}>
          <Card>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <K color={C.fg}>{m.meal_type}</K>
              <Text style={[s.strong, { fontVariant: ['tabular-nums'] }]}>{Math.round(m.energy_kcal)} kcal</Text>
            </View>
            <Text style={s.body}>{m.items.map((x: any) => `${x.name} (${Math.round(x.grams)} g)`).join(', ')}</Text>
          </Card>
        </FadeIn>
      ))}
      <Text style={s.muted}>Nutrition guidance only, not medical advice.</Text>
    </Screen>
  );
}
