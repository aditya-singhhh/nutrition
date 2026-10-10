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
  tagline: 'Know what’s on your plate', logIn: 'Log in', createAccount: 'Create account', email: 'Email', password: 'Password (10+ characters)',
  showPw: 'Show', hidePw: 'Hide', consent: 'I agree to the terms and consent to my health information being used to personalise nutrition guidance.',
  askTitle: 'Ask', askHello: 'Ask me anything about food. I use your profile and today’s meals to answer.', askPlaceholder: 'Ask about food or your health goal…',
  thinking: 'Thinking…', important: 'Important', sq1: 'What should I cook for dinner?', sq2: 'Is masala dosa ok for me?', sq3: 'Tips for my health goal', sq4: 'How much protein today?',
  tabBasics: 'Basics', tabGoals: 'Goals', tabHealth: 'Health', tabAccount: 'Account', saveProfile: 'Save profile', saved: 'Saved ✓', profileComplete: 'Profile complete',
  shareSummary: 'Share my 7-day food summary', logOut: 'Log out', deleteAccount: 'Delete my account',
  authHeadline: 'Eat well, without the guesswork', authB1: 'Scan any pack or plate', authB2: 'Advice that fits your health', authB3: 'Works in Hindi and English',
  welcomeBack: 'Welcome back', createYour: 'Create your account', newHere: 'New here? Create an account', haveOne: 'Already have an account? Log in',
  pwWeak: 'Weak', pwOk: 'Okay', pwStrong: 'Strong', pwNeed: 'At least 10 characters', badEmail: 'Enter a valid email address', advanced: 'Advanced', serverAddr: 'Server address',
  privacyNote: 'Your health details stay private to your account. You can delete them any time.',
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
  tagline: 'जानिए आपकी थाली में क्या है', logIn: 'लॉग इन', createAccount: 'खाता बनाएँ', email: 'ईमेल', password: 'पासवर्ड (कम से कम 10 अक्षर)',
  showPw: 'दिखाएँ', hidePw: 'छुपाएँ', consent: 'मैं शर्तों से सहमत हूँ और पोषण संबंधी सुझाव देने के लिए अपनी सेहत की जानकारी के उपयोग की अनुमति देता/देती हूँ।',
  askTitle: 'पूछें', askHello: 'खाने के बारे में कुछ भी पूछें। मैं आपकी प्रोफ़ाइल और आज के भोजन के हिसाब से जवाब देता हूँ।', askPlaceholder: 'खाने या सेहत के लक्ष्य के बारे में पूछें…',
  thinking: 'सोच रहे हैं…', important: 'ज़रूरी', sq1: 'आज रात खाने में क्या बनाऊँ?', sq2: 'क्या मसाला डोसा मेरे लिए ठीक है?', sq3: 'मेरे लक्ष्य के लिए सुझाव', sq4: 'आज कितना प्रोटीन लिया?',
  tabBasics: 'बुनियादी', tabGoals: 'लक्ष्य', tabHealth: 'सेहत', tabAccount: 'खाता', saveProfile: 'प्रोफ़ाइल सेव करें', saved: 'सेव हो गया ✓', profileComplete: 'प्रोफ़ाइल पूरी',
  shareSummary: 'मेरा 7 दिन का खान-पान सारांश भेजें', logOut: 'लॉग आउट', deleteAccount: 'मेरा खाता हटाएँ',
  authHeadline: 'सोच-समझकर खाइए', authB1: 'कोई भी पैक या थाली स्कैन करें', authB2: 'आपकी सेहत के हिसाब से सलाह', authB3: 'हिन्दी और अंग्रेज़ी में',
  welcomeBack: 'वापसी पर स्वागत है', createYour: 'अपना खाता बनाएँ', newHere: 'नए हैं? खाता बनाएँ', haveOne: 'पहले से खाता है? लॉग इन करें',
  pwWeak: 'कमज़ोर', pwOk: 'ठीक-ठाक', pwStrong: 'मज़बूत', pwNeed: 'कम से कम 10 अक्षर', badEmail: 'सही ईमेल पता लिखें', advanced: 'उन्नत', serverAddr: 'सर्वर का पता',
  privacyNote: 'आपकी सेहत की जानकारी सिर्फ़ आपके खाते में रहती है। आप इसे कभी भी हटा सकते हैं।',
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
