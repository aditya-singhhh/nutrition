import React, { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { Press } from '../anim';
import { api } from '../api';
import { useT } from '../i18n';
import { CountUp, FadeIn, FillBar, Ring } from '../anim';
import { C, F, SOFT_RED } from '../theme';
import { Bar, Card, K, Tag, s } from './ui';

const n = (v: unknown) => (typeof v === 'number' ? String(Math.round(v * 10) / 10) : '-');
const tone = (band?: string): 'ok' | 'warn' | 'bad' => (/good|great|excellent|healthy/i.test(band ?? '') ? 'ok' : /moderate|ok|fair/i.test(band ?? '') ? 'warn' : 'bad');
const ROWS: [string, string, string][] = [['Energy', 'energy_kcal', 'kcal'], ['Protein', 'protein_g', 'g'], ['Carbs', 'carbs_g', 'g'], ['Sugar', 'sugar_g', 'g'],
  ['Fat', 'fat_g', 'g'], ['Saturated fat', 'sat_fat_g', 'g'], ['Fibre', 'fiber_g', 'g'], ['Sodium', 'sodium_mg', 'mg']];
const ringColor = { ok: C.accent, warn: C.gold, bad: SOFT_RED };

export default function ResultView({ r, onOpen }: { r: any; onOpen?: (it: any) => void }) {
  const { t: tr } = useT();
  const [open, setOpen] = useState(false);
  const [alts, setAlts] = useState<any>(null);
  const key = r.type === 'food' ? r.slug : r.barcode;
  const wantAlts = r.quality_score?.score != null && !!onOpen && !!key && !['everyday'].includes(r.verdict?.code);
  useEffect(() => {
    setAlts(null);
    if (!wantAlts) return;
    let live = true;
    api.alternatives(r.type === 'food' ? { slug: r.slug } : { barcode: r.barcode }).then((a: any) => { if (live) setAlts(a); }).catch(() => {});
    return () => { live = false; };
  }, [key, wantAlts]); // eslint-disable-line react-hooks/exhaustive-deps
  const q = r.quality_score ?? {};
  const pc = r.personal_compatibility ?? {};
  const nut = r.nutrition_for_portion;
  const per100 = r.nutrition_per_100g;
  const additives: any[] = (r.ingredients?.additives ?? []).filter((a: any) => a.category !== 'generally_recognized');
  const t = tone(q.band);
  const vd = r.verdict;
  const hh = r.household;
  const trust = r.data_quality?.trust;
  let d = 0;
  const next = () => 80 * d++;
  return (
    <View style={{ gap: 14 }}>
      <FadeIn delay={next()}>
        <Text style={{ fontFamily: F.display, fontSize: 26, lineHeight: 31, color: C.fg }}>{r.name ?? 'Scanned product'}</Text>
        <Text style={s.muted}>{[r.type !== 'food' && r.brand, r.portion && `${r.portion.label} · ${n(r.portion.grams)} g`].filter(Boolean).join(' · ')}</Text>
      </FadeIn>

      {vd && (
        <FadeIn delay={next()}>
          <Card tone={vd.tone === 'ok' ? 'ok' : vd.tone === 'warn' ? 'warn' : vd.tone === 'bad' ? 'bad' : undefined}>
            <Text style={{ fontFamily: F.display, fontSize: 26, lineHeight: 31, color: C.fg }}>{tr(('v_' + vd.code) as any)}</Text>
            {vd.reasons?.slice(0, 2).map((x: any, i: number) => (
              <Text key={i} style={s.body}>• {tr(('r_' + x.code) as any, { v: x.value ?? '' })}</Text>
            ))}
            {hh && (
              <Text style={s.muted}>
                {[hh.sugar_tsp != null && `${hh.sugar_tsp} ${tr('tsp')} ${tr('sugarTsp')}`, hh.salt_tsp != null && `${hh.salt_tsp} ${tr('tsp')} ${tr('saltTsp')}`, hh.fat_tsp != null && `${hh.fat_tsp} ${tr('tsp')} ${tr('fatTsp')}`].filter(Boolean).join(' · ')}
              </Text>
            )}
          </Card>
        </FadeIn>
      )}
      {trust && <Text style={s.muted}>{tr(('t_' + trust) as any)}</Text>}

      {q.score != null ? (
        <FadeIn delay={next()}>
          <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 18 }}>
            <Ring value={q.score} color={ringColor[t]} track={C.track}>
              <CountUp value={q.score} style={{ fontFamily: F.display, fontSize: 40, color: C.fg }} />
              <K size={9}>{tr('outOf')}</K>
            </Ring>
            <View style={{ flex: 1, gap: 8 }}>
              <K>{tr('qualityScore')}</K>
              <Tag label={q.band} tone={t} />
            </View>
          </Card>
        </FadeIn>
      ) : (
        <FadeIn delay={next()}>
          <Card tone="warn">
            <K color={C.warn}>{tr('noScore')}</K>
            <Text style={s.body}>{tr('noScoreWhy')}</Text>
          </Card>
        </FadeIn>
      )}

      {r.daily_share?.items?.filter((d: any) => d.pct >= 10).length > 0 && (
        <FadeIn delay={next()}>
          <Card>
            <K>{tr('oneServing')}</K>
            {r.daily_share.items.filter((d: any) => d.pct >= 10).slice(0, 3).map((d: any) => (
              <Bar key={d.key} label={d.label} value={d.amount} max={d.limit} unit={d.unit} limit />
            ))}
          </Card>
        </FadeIn>
      )}

      {alts && alts.status !== 'unknown_category' && alts.status !== 'no_score' && (
        <FadeIn delay={next()}>
          <Card>
            <K>{tr('better')}</K>
            {alts.items.length === 0 && <Text style={s.muted}>{tr('betterNone')}</Text>}
            {alts.items.map((it: any) => (
              <Press key={it.id} accessibilityRole="button" onPress={() => onOpen?.(it)} style={{ minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ flex: 1 }}>
                  <Text numberOfLines={1} style={{ fontFamily: F.bodyBold, fontSize: 16, color: C.fg }}>{it.name}</Text>
                  <Text numberOfLines={1} style={s.muted}>{[it.brand, ...it.why.map((w: any) => `${w.pct}% ${tr(('better' + w.code.charAt(0).toUpperCase() + w.code.slice(1)) as any)}`)].filter(Boolean).join(' · ')}</Text>
                </View>
                <Tag label={String(it.score)} tone="ok" />
              </Press>
            ))}
          </Card>
        </FadeIn>
      )}

      {r.label_warnings?.length > 0 && (
        <FadeIn delay={next()}><Card tone="warn"><K color={C.warn}>{tr('checkPack')}</K>{r.label_warnings.slice(0, 2).map((w: string, i: number) => <Text key={i} style={s.body}>• {w}</Text>)}</Card></FadeIn>
      )}

      {(pc.alerts?.length > 0 || (open && (pc.notes?.length > 0 || pc.overall != null))) && (
        <FadeIn delay={next()}>
          <Card tone={pc.blocked ? 'bad' : pc.alerts?.length ? 'warn' : undefined}>
            <K color={pc.blocked ? C.bad : C.fg}>{tr('forYou')}</K>
            {pc.alerts?.map((a: any, i: number) => <Text key={i} style={[s.body, { fontFamily: F.bodyBold }]}>{a.message}</Text>)}
            {open && pc.overall != null && !pc.blocked && <Text style={s.body}>Fit for your profile: {pc.overall}/100 ({pc.label})</Text>}
            {open && pc.conditions?.flatMap((c: any) => c.details.filter((x: any) => x.verdict === 'unfavourable')
              .map((x: any) => <Text key={c.condition + x.metric} style={s.body}>• {c.label}: {x.metric.replace('_', ' ')} {n(x.value)} {x.unit}. {x.why_it_matters}</Text>))}
            {open && pc.notes?.map((x: string, i: number) => <Text key={i} style={s.muted}>{x}</Text>)}
          </Card>
        </FadeIn>
      )}

      {open && q.components?.length > 0 && (
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

      {open && (nut || per100) && (
        <FadeIn delay={next()}>
          <Card>
            <K>{tr('facts')}</K>
            <View style={{ flexDirection: 'row', paddingTop: 4 }}>
              <View style={{ flex: 1.2 }} />
              {nut && <View style={{ flex: 1, alignItems: 'flex-end' }}><K size={9}>{r.portion?.grams ? `Per serving · ${n(r.portion.grams)} g` : 'Per portion'}</K></View>}
              {per100 && <View style={{ flex: 1, alignItems: 'flex-end' }}><K size={9}>{tr('per100')}</K></View>}
            </View>
            {ROWS.map(([l, key, u]) => (
              <View key={key} style={{ flexDirection: 'row', borderTopWidth: 1, borderColor: C.line, paddingTop: 8 }}>
                <Text style={[s.body, { flex: 1.2 }]}>{l}</Text>
                {nut && <Text style={[s.body, { flex: 1, textAlign: 'right', fontVariant: ['tabular-nums'], fontFamily: F.bodyBold }]}>{n(nut[key])}{nut[key] == null ? '' : ` ${u}`}</Text>}
                {per100 && <Text style={[s.body, { flex: 1, textAlign: 'right', fontVariant: ['tabular-nums'], color: C.muted }]}>{n(per100[key])}{per100[key] == null ? '' : ` ${u}`}</Text>}
              </View>
            ))}
            <Text style={s.muted}>{tr('unknownDash')}</Text>
          </Card>
        </FadeIn>
      )}

      {open && additives.length > 0 && (
        <FadeIn delay={next()}>
          <Card>
            <K>{tr('additives')}</K>
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
        <FadeIn delay={next()}><Card tone="bad"><K color={C.bad}>{tr('contains')}</K><Text style={s.body}>{r.ingredients.allergens.join(', ')}</Text></Card></FadeIn>
      )}

      {(q.components?.length > 0 || additives.length > 0 || nut || per100) && (
        <Press accessibilityRole="button" onPress={() => setOpen(!open)} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ fontFamily: F.bodyBold, fontSize: 15, color: C.accent }}>{open ? tr('hide') : tr('seeHow')}</Text>
        </Press>
      )}
      <Text style={s.muted}>{tr('disclaimer')}</Text>
    </View>
  );
}
