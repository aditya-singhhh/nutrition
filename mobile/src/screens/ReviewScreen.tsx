import React, { useCallback, useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { FadeIn, Press } from '../anim';
import { api } from '../api';
import Screen from '../components/Screen';
import { Button, Card, Display, ErrorText, K, Tag, s } from '../components/ui';
import { C, F } from '../theme';

/** Admin-only: approve products so they show as "checked by us". Most-confirmed first. */
export default function ReviewScreen({ onClose }: { onClose: () => void }) {
  const [items, setItems] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setItems((await api.reviewQueue()).items); setErr(null); } catch (e: any) { setErr(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);
  async function approve(code: string) {
    setBusy(code);
    try { await api.reviewProduct(code, true); setItems((x) => x.filter((i) => i.barcode !== code)); } catch (e: any) { setErr(e.message); } finally { setBusy(null); }
  }
  const n = (v: any, u: string) => (typeof v === 'number' ? `${Math.round(v * 10) / 10} ${u}` : '-');
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <Screen>
        <Button kind="tonal" title="Back" onPress={onClose} style={{ height: 44 }} />
        <Display size={34}>Review products</Display>
        <ErrorText>{err}</ErrorText>
        {items.length === 0 && !err && <Text style={s.muted}>Nothing waiting for review.</Text>}
        {items.map((i, k) => {
          const p = i.nutrients_per_100g ?? {};
          return (
            <FadeIn key={i.barcode} delay={k * 30}>
              <Card>
                <Text style={{ fontFamily: F.bodyBold, fontSize: 16, color: C.fg }}>{i.name}</Text>
                <Text style={s.muted}>{[i.brand, i.category, i.barcode].join(' · ')}</Text>
                <Text style={s.body}>Per 100 g: {n(p.energy_kcal, 'kcal')} · sugar {n(p.sugar_g, 'g')} · sat fat {n(p.sat_fat_g, 'g')} · sodium {n(p.sodium_mg, 'mg')}</Text>
                <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                  <Tag tone={i.trust === 'community_confirmed' ? 'ok' : 'warn'} label={i.trust.replace('_', ' ')} />
                  <K>{i.scans} scans · {i.confirmations} agree</K>
                </View>
                <Press accessibilityRole="button" disabled={busy === i.barcode} onPress={() => approve(i.barcode)} style={{ minHeight: 44, justifyContent: 'center' }}>
                  <Text style={{ fontFamily: F.bodyBold, fontSize: 15, color: C.accent }}>Compare with the pack, then mark checked</Text>
                </Press>
              </Card>
            </FadeIn>
          );
        })}
      </Screen>
    </View>
  );
}
