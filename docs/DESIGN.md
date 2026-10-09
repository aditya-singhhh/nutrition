# Design and UX principles (India first)

1. **Verdict before numbers.** Shoppers want "can I have this?", not "54/100". Each result opens with one calm sentence (good everyday choice, fine in small amounts, okay now and then, best kept for special occasions), then the reasons, then the score. The verdict comes from fixed rules in `services/verdict.py`, never from AI.
2. **Household measures.** Sugar, salt and ghee/oil are also shown in teaspoons (sugar 4 g, salt 5 g, fat 5 g per teaspoon), because grams mean little at the kitchen counter.
3. **Portion-aware, not food-shaming.** Ghee, achar, mithai and chai are part of life. A food that scores low but is eaten in a small portion is "fine in small amounts", with the percentage of the daily limit shown. Alarm colours are reserved for allergens and real limits.
4. **Visible trust.** Every product says where its numbers came from: checked by us, confirmed by several users' scans (different users, values within 10%), one user's scan, or community data. Unchecked data never looks official.
5. **Hindi and English** with one tap (Home). Numbers and verdicts are rendered from codes, so both languages say the same thing. Remaining screens (Profile, Ask, sign-in) are still English-only.
6. **Quiet interface.** Sentence case, a warm off-white background, softer reds, cards instead of heavy borders, and details (score breakdown, additives) hidden behind "See how we worked this out". Big text and 44 px touch targets for older users and cheap phones.
7. **Low-end phones and weak networks.** Photos are compressed before upload, requests time out with a clear message, animations respect reduce-motion, and the server cold start is explained instead of showing an error.
8. **Doctor first.** Conditions (diabetes, blood pressure, cholesterol) tighten the verdict, never loosen it. The disclaimer asks the user to follow their doctor.

Not done yet: Hindi for all screens, regional languages, FSSAI vegetarian/non-vegetarian mark, "healthier alternatives" (needs a bigger verified product table first), voice input.
