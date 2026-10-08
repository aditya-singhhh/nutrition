import React from 'react';
import { Text, View } from 'react-native';
import { DISCLAIMER } from '../theme';
import { Card, s } from './ui';

const n = (v: unknown) => (typeof v === 'number' ? String(Math.round(v * 10) / 10) : '-');

export default function ResultView({ r }: { r: any }) {
  const q = r.quality_score ?? {};
  const pc = r.personal_compatibility ?? {};
  const nut = r.nutrition_for_portion ?? {};
  const additives: any[] = (r.ingredients?.additives ?? []).filter((a: any) => a.category !== 'generally_recognized');
  return (
    <View style={{ gap: 12 }}>
      <Card>
        <Text style={s.h2}>{r.brand ? `${r.brand} ${r.name}` : r.name}</Text>
        <Text style={s.muted}>Per {r.portion?.label} (about {n(r.portion?.grams)} g)</Text>
        <Text style={s.body}>
          {n(nut.energy_kcal)} kcal · {n(nut.protein_g)} g protein · {n(nut.carbs_g)} g carbs · {n(nut.fat_g)} g fat
        </Text>
        <Text style={s.body}>
          Sugar {n(nut.sugar_g)} g · Sodium {n(nut.sodium_mg)} mg · Fibre {n(nut.fiber_g)} g
        </Text>
      </Card>

      <Card>
        <Text style={s.h2}>Quality score</Text>
        {q.score == null ? <Text style={s.muted}>Not enough data to score this food.</Text> : (
          <>
            <Text style={{ fontSize: 34, fontWeight: '700' }}>{q.score}<Text style={s.muted}> / 100 · {q.band}</Text></Text>
            <Text style={s.muted}>{q.summary} Confidence: {q.confidence}.</Text>
            {q.components?.map((c: any) => (
              <Text key={c.key} style={s.body}>• {c.label}: {c.explanation}</Text>
            ))}
          </>
        )}
      </Card>

      {(pc.alerts?.length > 0 || pc.overall != null || pc.notes?.length > 0) && (
        <Card tone={pc.blocked ? 'bad' : undefined}>
          <Text style={s.h2}>For you</Text>
          {pc.alerts?.map((a: any, i: number) => <Text key={i} style={[s.body, { fontWeight: '600' }]}>{a.message}</Text>)}
          {pc.overall != null && !pc.blocked && <Text style={s.body}>Compatibility {pc.overall}/100 ({pc.label})</Text>}
          {pc.conditions?.flatMap((c: any) => c.details.filter((d: any) => d.verdict === 'unfavourable')
            .map((d: any) => <Text key={c.condition + d.metric} style={s.body}>• {c.label}: {d.metric.replace('_', ' ')} {n(d.value)} {d.unit}, {d.why_it_matters}</Text>))}
          {pc.notes?.map((t: string, i: number) => <Text key={i} style={s.muted}>{t}</Text>)}
        </Card>
      )}

      {additives.length > 0 && (
        <Card>
          <Text style={s.h2}>Additives worth knowing</Text>
          {additives.map((a) => <Text key={a.ins} style={s.body}>• INS {a.ins} {a.name} ({a.category.replace(/_/g, ' ')})</Text>)}
        </Card>
      )}

      {r.data_quality?.warning && <Card tone="warn"><Text style={s.body}>{r.data_quality.warning}</Text></Card>}
      <Text style={s.muted}>{DISCLAIMER}</Text>
    </View>
  );
}
