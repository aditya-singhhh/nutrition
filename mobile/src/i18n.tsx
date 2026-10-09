import * as SecureStore from 'expo-secure-store';
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

export type Lang = 'en' | 'hi';

const EN = {
  home: 'Home', scan: 'Scan', ask: 'Ask', profile: 'Profile', today: 'Today',
  point: 'Scan a barcode, plate or label', pointSub: '',
  gallery: 'Gallery', type: 'Type', analysing: 'Looking…', slow: 'Still working… the server may be waking up',
  cameraNeeded: 'Camera needed', allowCamera: 'Allow camera',
  cameraWhy: 'Allow the camera to scan, or use Gallery.',
  pickPack: 'Which pack is yours?', back: 'Back',
  pickPackHelp: 'We read “{name}”. Pick the one that matches your pack size.',
  logServing: 'Add to today', logged: 'Added to today.',
  // verdicts
  v_everyday: 'A good everyday choice', v_fine: 'Fine to have regularly', v_small_ok: 'Fine in small amounts',
  v_sometimes: 'Okay now and then', v_rarely: 'Best kept for special occasions', v_avoid: 'Not safe for you', v_unknown: 'We can’t judge this yet',
  r_high_sat_fat: 'One serving has {v}% of a day’s saturated fat', r_high_sugar: 'One serving has {v}% of a day’s sugar',
  r_high_sodium: 'One serving has {v}% of a day’s salt', r_not_ideal_for_you: 'Not the best match for your health profile',
  r_allergen: 'It contains something you are allergic to',
  inSpoons: 'In spoons', sugarTsp: 'sugar', saltTsp: 'salt', fatTsp: 'fat (ghee or oil)', tsp: 'tsp',
  oneServing: 'One serving uses', basedOn: 'Based on {x}.',
  qualityScore: 'Quality score', outOf: 'out of 100', noScore: 'No score yet',
  seeHow: 'See how we worked this out', hide: 'Hide', facts: 'Nutrition facts', perServing: 'Per serving', per100: 'Per 100 g',
  unknownDash: 'A dash means the value is not known. We never assume zero.',
  additives: 'Additives and what they are', contains: 'Contains', forYou: 'For you', checkPack: 'Check these against the pack',
  t_verified: 'Checked by us', t_community_confirmed: 'Confirmed by several scans', t_from_scan: 'From a user’s scan · unchecked',
  t_community: 'Community data · unchecked',
  disclaimer: 'Guidance only, not medical advice.',
  better: 'Healthier options', betterNone: 'No better match found yet. More scans improve this.', betterLess_sugar: 'less sugar', betterLess_salt: 'less salt', betterLess_sat_fat: 'less saturated fat', betterMore_fibre: 'more fibre', betterMore_protein: 'more protein', vs: 'vs this',
  language: 'Language', noScoreWhy: 'Not enough data to judge this. Scan its nutrition table.',
};
const HI: typeof EN = {
  home: 'होम', scan: 'स्कैन', ask: 'पूछें', profile: 'प्रोफ़ाइल', today: 'आज',
  point: 'बारकोड, थाली या लेबल की तरफ़ कैमरा रखें', pointSub: '',
  gallery: 'गैलरी', type: 'लिखें', analysing: 'देख रहे हैं…', slow: 'थोड़ा समय लग रहा है… सर्वर शुरू हो रहा होगा',
  cameraNeeded: 'कैमरा चाहिए', allowCamera: 'कैमरा चालू करें',
  cameraWhy: 'स्कैन के लिए कैमरा चालू करें, या गैलरी चुनें।',
  pickPack: 'आपका पैक कौन-सा है?', back: 'वापस',
  pickPackHelp: 'हमने “{name}” पढ़ा। अपने पैक के साइज़ से मिलता हुआ चुनें।',
  logServing: 'आज में जोड़ें', logged: 'आज में जोड़ दिया।',
  v_everyday: 'रोज़ खाने के लिए अच्छा', v_fine: 'नियमित रूप से खा सकते हैं', v_small_ok: 'थोड़ी मात्रा में ठीक है',
  v_sometimes: 'कभी-कभार ठीक है', v_rarely: 'खास मौकों पर ही खाएँ', v_avoid: 'आपके लिए सुरक्षित नहीं', v_unknown: 'अभी इसका आकलन नहीं कर सकते',
  r_high_sat_fat: 'एक सर्विंग में दिन की {v}% संतृप्त वसा है', r_high_sugar: 'एक सर्विंग में दिन की {v}% चीनी है',
  r_high_sodium: 'एक सर्विंग में दिन का {v}% नमक है', r_not_ideal_for_you: 'आपकी सेहत की प्रोफ़ाइल के लिए सबसे अच्छा नहीं',
  r_allergen: 'इसमें वह चीज़ है जिससे आपको एलर्जी है',
  inSpoons: 'चम्मच में', sugarTsp: 'चीनी', saltTsp: 'नमक', fatTsp: 'वसा (घी या तेल)', tsp: 'छोटा चम्मच',
  oneServing: 'एक सर्विंग में', basedOn: 'आधार: {x}।',
  qualityScore: 'क्वालिटी स्कोर', outOf: '100 में से', noScore: 'अभी स्कोर नहीं',
  seeHow: 'यह कैसे निकाला, देखें', hide: 'छुपाएँ', facts: 'न्यूट्रिशन जानकारी', perServing: 'प्रति सर्विंग', per100: 'प्रति 100 ग्राम',
  unknownDash: 'डैश का मतलब है कि मान पता नहीं। हम कभी शून्य नहीं मानते।',
  additives: 'एडिटिव और वे क्या हैं', contains: 'इसमें है', forYou: 'आपके लिए', checkPack: 'इन्हें पैक से मिलाकर देखें',
  t_verified: 'हमारे द्वारा जाँचा गया', t_community_confirmed: 'कई यूज़र्स के स्कैन से पुष्ट', t_from_scan: 'यूज़र के स्कैन से · अजाँचा',
  t_community: 'कम्युनिटी डेटा · अजाँचा',
  disclaimer: 'सिर्फ़ जानकारी है, चिकित्सकीय सलाह नहीं।',
  better: 'बेहतर विकल्प', betterNone: 'अभी कोई बेहतर विकल्प नहीं मिला। ज़्यादा स्कैन से यह बेहतर होगा।', betterLess_sugar: 'कम चीनी', betterLess_salt: 'कम नमक', betterLess_sat_fat: 'कम संतृप्त वसा', betterMore_fibre: 'ज़्यादा फ़ाइबर', betterMore_protein: 'ज़्यादा प्रोटीन', vs: 'इसकी तुलना में',
  language: 'भाषा', noScoreWhy: 'आँकड़े कम हैं। इसकी न्यूट्रिशन टेबल स्कैन करें।',
};
const DICT = { en: EN, hi: HI };
export type Key = keyof typeof EN;

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (k: Key, vars?: Record<string, string | number>) => string };
const I18n = createContext<Ctx>({ lang: 'en', setLang: () => {}, t: (k) => EN[k] });

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setL] = useState<Lang>('en');
  useEffect(() => { SecureStore.getItemAsync('hc_lang').then((v) => { if (v === 'hi' || v === 'en') setL(v); }).catch(() => {}); }, []);
  const setLang = useCallback((l: Lang) => { setL(l); SecureStore.setItemAsync('hc_lang', l).catch(() => {}); }, []);
  const t = useCallback((k: Key, vars?: Record<string, string | number>) => {
    let s: string = DICT[lang][k] ?? EN[k] ?? String(k);
    if (vars) for (const [a, b] of Object.entries(vars)) s = s.replace(`{${a}}`, String(b));
    return s;
  }, [lang]);
  return <I18n.Provider value={{ lang, setLang, t }}>{children}</I18n.Provider>;
}
export const useT = () => useContext(I18n);
