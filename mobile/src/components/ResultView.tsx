import React from 'react';
import { Text, View } from 'react-native';
import { CountUp, FadeIn, FillBar, Ring } from '../anim';
import { C, DISCLAIMER, F } from '../theme';
import { Card, K, Tag, s } from './ui';

const n = (v: unknown) => (typeof v === 'number' ? String(Math.round(v * 10) / 10) : '-');
const tone = (band?: string): 'ok' | 'warn' | 'bad' => (/good|great|excellent|healthy/i.test(band ?? '') ? 'ok' : /moderate|ok|fair/i.test(band ?? '') ? 'warn' : 'bad');
const ringColor = { ok: C.accent, warn: C.gold, bad: '#C8402F' };

export default function ResultView({ r }: { r: any }) {
  const q = r.quality_score ?? {};
  const pc = r.personal_compatibility ?? {};
  const nut = r.nutrition_for_portion;
  const additives: any[] = (r.ingredients?.additives ?? []).filter((a: any) => a.category !== 'generally_recognized');
  const t = tone(q.band);
  let d = 0;
  const next = () => 80 * d++;
  return (
    <View style={{ gap: 14 }}>
      <FadeIn delay={next()}>
        <Card>
          <K>{r.type === 'food' ? 'Dish' : r.brand ?? 'Scanned label'}</K>
          <Text style={{ fontFamily: F.display, fontSize: 30, lineHeight: 31, textTransform: 'uppercase', color: C.fg }}>{r.name ?? 'Scanned product'}</Text>
          {r.portion && <Text style={s.muted}>Per {r.portion.label} · about {n(r.portion.grams)} g</Text>}
        </Card>
      </FadeIn>

      {q.score != null ? (
        <FadeIn delay={next()}>
          <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 18 }}>
            <Ring value={q.score} color={ringColor[t]} track={C.track}>
              <CountUp value={q.score} style={{ fontFamily: F.display, fontSize: 40, color: C.fg }} />
              <K size={9}>of 100</K>
            </Ring>
            <View style={{ flex: 1, gap: 8 }}>
              <K>Quality score</K>
              <Tag label={q.band} tone={t} />
              <Text style={s.muted}>{q.summary}</Text>
            </View>
          </Card>
        </FadeIn>
      ) : (
        <FadeIn delay={next()}><Card tone="warn"><Text style={s.body}>Not enough nutrition data to give a score.</Text></Card></FadeIn>
      )}

      {(pc.alerts?.length > 0 || pc.notes?.length > 0 || (pc.overall != null && !pc.blocked)) && (
        <FadeIn delay={next()}>
          <Card tone={pc.blocked ? 'bad' : pc.alerts?.length ? 'warn' : undefined}>
            <K color={pc.blocked ? C.bad : C.fg}>For you</K>
            {pc.alerts?.map((a: any, i: number) => <Text key={i} style={[s.body, { fontFamily: F.bodyBold }]}>{a.message}</Text>)}
            {pc.overall != null && !pc.blocked && <Text style={s.body}>Fit for your profile: {pc.overall}/100 ({pc.label})</Text>}
            {pc.conditions?.flatMap((c: any) => c.details.filter((x: any) => x.verdict === 'unfavourable')
              .map((x: any) => <Text key={c.condition + x.metric} style={s.body}>• {c.label}: {x.metric.replace('_', ' ')} {n(x.value)} {x.unit}. {x.why_it_matters}</Text>))}
            {pc.notes?.map((x: string, i: number) => <Text key={i} style={s.muted}>{x}</Text>)}
          </Card>
        </FadeIn>
      )}

      {q.components?.length > 0 && (
        <FadeIn delay={next()}>
          <Card>
            <K>Score breakdown</K>
            {q.components.map((c: any) => (
              <View key={c.key} style={{ gap: 5 }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                  <Text style={[s.body, { fontFamily: F.bodyMed }]}>{c.label}</Text>
                  <Text style={s.muted}>{n(c.value)} {c.unit}</Text>
                </View>
                <FillBar pct={c.subscore ?? 0} color={c.subscore >= 66 ? C.accent : c.subscore >= 33 ? C.gold : '#C8402F'} track={C.track} height={6} />
              </View>
            ))}
          </Card>
        </FadeIn>
      )}

      {nut && (
        <FadeIn delay={next()}>
          <Card>
            <K>Nutrition facts</K>
            {([['Energy', nut.energy_kcal, 'kcal'], ['Protein', nut.protein_g, 'g'], ['Carbs', nut.carbs_g, 'g'], ['Fat', nut.fat_g, 'g'],
              ['Sugar', nut.sugar_g, 'g'], ['Fibre', nut.fiber_g, 'g'], ['Sodium', nut.sodium_mg, 'mg']] as const).map(([l, v, u]) => (
              <View key={l} style={{ flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 1, borderColor: C.line, paddingTop: 8 }}>
                <Text style={s.body}>{l}</Text>
                <Text style={[s.body, { fontVariant: ['tabular-nums'], fontFamily: F.bodyBold }]}>{n(v)} {v == null ? '' : u}</Text>
              </View>
            ))}
          </Card>
        </FadeIn>
      )}

      {additives.length > 0 && (
        <FadeIn delay={next()}>
          <Card>
            <K>Additives worth knowing</K>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {additives.map((a) => <Tag key={a.ins} tone="warn" label={`INS ${a.ins} ${a.name}`} />)}
            </View>
          </Card>
        </FadeIn>
      )}

      {r.ingredients?.allergens?.length > 0 && (
        <FadeIn delay={next()}><Card tone="bad"><K color={C.bad}>Contains</K><Text style={s.body}>{r.ingredients.allergens.join(', ')}</Text></Card></FadeIn>
      )}

      {r.data_quality?.warning && <FadeIn delay={next()}><Card tone="warn"><Text style={s.body}>{r.data_quality.warning}</Text></Card></FadeIn>}
      <Text style={s.muted}>{DISCLAIMER}</Text>
    </View>
  );
}
