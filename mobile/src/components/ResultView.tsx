import React from 'react';
import { Text, View } from 'react-native';
import { CountUp, FadeIn, FillBar, Ring } from '../anim';
import { C, DISCLAIMER, F } from '../theme';
import { Bar, Card, K, Tag, s } from './ui';

const n = (v: unknown) => (typeof v === 'number' ? String(Math.round(v * 10) / 10) : '-');
const tone = (band?: string): 'ok' | 'warn' | 'bad' => (/good|great|excellent|healthy/i.test(band ?? '') ? 'ok' : /moderate|ok|fair/i.test(band ?? '') ? 'warn' : 'bad');
const ROWS: [string, string, string][] = [['Energy', 'energy_kcal', 'kcal'], ['Protein', 'protein_g', 'g'], ['Carbs', 'carbs_g', 'g'], ['Sugar', 'sugar_g', 'g'],
  ['Fat', 'fat_g', 'g'], ['Saturated fat', 'sat_fat_g', 'g'], ['Fibre', 'fiber_g', 'g'], ['Sodium', 'sodium_mg', 'mg']];
const ringColor = { ok: C.accent, warn: C.gold, bad: '#C8402F' };

export default function ResultView({ r }: { r: any }) {
  const q = r.quality_score ?? {};
  const pc = r.personal_compatibility ?? {};
  const nut = r.nutrition_for_portion;
  const per100 = r.nutrition_per_100g;
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
        <FadeIn delay={next()}>
          <Card tone="warn">
            <K color={C.warn}>No score yet</K>
            <Text style={s.body}>{q.summary ?? 'Not enough nutrition data to give a score.'}</Text>
            {q.score_range && <Text style={s.muted}>With what we know so far it could land anywhere between {q.score_range.min} and {q.score_range.max} out of 100, so we won't show a single number.</Text>}
          </Card>
        </FadeIn>
      )}

      {r.daily_share?.items?.length > 0 && (
        <FadeIn delay={next()}>
          <Card>
            <K>One serving uses</K>
            {r.daily_share.items.map((d: any) => (
              <Bar key={d.key} label={d.label} value={d.amount} max={d.limit} unit={d.unit} limit />
            ))}
            <Text style={s.muted}>Based on {r.daily_share.basis}.</Text>
          </Card>
        </FadeIn>
      )}

      {r.label_warnings?.length > 0 && (
        <FadeIn delay={next()}><Card tone="warn"><K color={C.warn}>Check these against the pack</K>{r.label_warnings.map((w: string, i: number) => <Text key={i} style={s.body}>• {w}</Text>)}</Card></FadeIn>
      )}
      {r.created_from_label && (
        <FadeIn delay={next()}><Card tone="ok"><Text style={s.body}>Saved from your scan, so the next person who scans this barcode gets an answer. It stays marked as unverified.</Text></Card></FadeIn>
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

      {(nut || per100) && (
        <FadeIn delay={next()}>
          <Card>
            <K>Nutrition facts</K>
            <View style={{ flexDirection: 'row', paddingTop: 4 }}>
              <View style={{ flex: 1.2 }} />
              {nut && <View style={{ flex: 1, alignItems: 'flex-end' }}><K size={9}>{r.portion?.grams ? `Per serving · ${n(r.portion.grams)} g` : 'Per portion'}</K></View>}
              {per100 && <View style={{ flex: 1, alignItems: 'flex-end' }}><K size={9}>Per 100 g</K></View>}
            </View>
            {ROWS.map(([l, key, u]) => (
              <View key={key} style={{ flexDirection: 'row', borderTopWidth: 1, borderColor: C.line, paddingTop: 8 }}>
                <Text style={[s.body, { flex: 1.2 }]}>{l}</Text>
                {nut && <Text style={[s.body, { flex: 1, textAlign: 'right', fontVariant: ['tabular-nums'], fontFamily: F.bodyBold }]}>{n(nut[key])}{nut[key] == null ? '' : ` ${u}`}</Text>}
                {per100 && <Text style={[s.body, { flex: 1, textAlign: 'right', fontVariant: ['tabular-nums'], color: C.muted }]}>{n(per100[key])}{per100[key] == null ? '' : ` ${u}`}</Text>}
              </View>
            ))}
            <Text style={s.muted}>A dash means the value is not known. We never assume zero.</Text>
          </Card>
        </FadeIn>
      )}

      {additives.length > 0 && (
        <FadeIn delay={next()}>
          <Card>
            <K>Additives and what they are</K>
            {additives.map((a) => (
              <View key={a.ins} style={{ gap: 4, borderTopWidth: 1, borderColor: C.line, paddingTop: 10 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <Text style={{ fontFamily: F.bodyBold, fontSize: 15, color: C.fg }}>INS {a.ins} · {a.name}</Text>
                  <Tag tone={a.category === 'high_concern' ? 'bad' : 'warn'} label={`${a.function} · ${String(a.category).replace(/_/g, ' ')}`} />
                </View>
                <Text style={s.muted}>{a.explanation}</Text>
              </View>
            ))}
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
