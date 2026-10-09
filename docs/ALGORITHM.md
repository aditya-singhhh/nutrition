# How Health Companion works: the core algorithm

One sentence: **identify what the person is eating, look up its nutrition from trusted tables, score it, check it against *their* profile and today's intake, and say it plainly.** AI is allowed to *recognise* things. It is never allowed to *decide numbers or give medical advice*.

All thresholds below are **placeholders pending clinical review** (`status: NEEDS_CLINICAL_REVIEW` in the config files). They live in JSON (`backend/app/data/`), not in code, so a dietitian can change them without a developer.

---

## 0. The three rules everything follows

1. **AI never invents nutrition.** Gemini may name a dish, read label text or read a barcode number. Every calorie, gram and milligram comes from our tables or the printed label, and is computed by plain arithmetic.
2. **Unknown is not zero.** A missing value stays missing, is left out of scores and totals, and lowers the stated confidence. We never fill gaps with guesses.
3. **Safety first, with fixed replies.** Emergencies and self-harm get a fixed, pre-written reply. The AI is not called at all. Allergen matches block a food outright.

---

## 1. The pipeline

```
 INPUT                IDENTIFY                  NUTRITION             JUDGE                      OUTPUT
 camera/gallery ──►  1. Barcode?  ───────────►  product table  ──►   quality score      ──►  result card
 typed barcode        2. Label text? ─────────►  parse ingredients     (0-100, explained)       + "for you" alerts
 typed dish name      3. Food photo? ─────────►  food table x grams    personal compatibility   + log to today
                      4. Typed search ────────►  food table            (profile-aware)          + daily totals
                                                                       ──► recommendations
```

### 1.1 Identify: which route a scan takes

| Step | Trigger | What happens | Where the numbers come from |
|---|---|---|---|
| 1 | Camera reads a barcode (EAN-13, EAN-8, UPC-A/E) or the user types one | Look up the code. Order: **our product table** → **Open Food Facts** (tries the code as written, zero-padded to 13 digits, and without leading zeros) → "not found" | Product table or Open Food Facts label values |
| 2 | User taps the scan button; the photo goes to the server as one request | Gemini decides: *food*, *packaged product with a readable barcode number*, *ingredient label*, or *none* | See below |
| 2a | *product* | Read the digits, then repeat step 1 | As step 1 |
| 2b | *label* | Gemini copies what is printed: the **ingredient list** and the **nutrition table** (per 100 g and/or per serving, plus the serving size in grams). We then **validate** the table (section 1.3), parse the ingredients and additives ourselves, and score | The printed table, after validation. No table → ingredients only → **no score** |
| 2c | *food* | Gemini names each dish and estimates a gram range. We match the name to our food table: exact id first, then name/alias search. Unmatched dishes are **listed by name with no numbers** | Our food table × grams |
| 3 | Typed dish search | Name/alias search over the food table | Food table |

Gallery pictures take the same route as camera pictures.

### 1.3 Reading a nutrition table safely

The reader is not trusted. `domain/label.py` does the following:
1. Keeps only numbers that are finite and in a plausible range. Salt is converted to sodium (1 g salt = 400 mg sodium).
2. Uses the **per 100 g** column if it has at least 4 values. Otherwise it scales the **per serving** column by the printed serving size. If neither works, the table is ignored and the user is told to rescan.
3. Refuses a table where protein + carbs + fat exceed 100 g per 100 g.
4. Drops saturated fat if it exceeds total fat, and sugar if it exceeds carbohydrate, with a warning.
5. Warns if energy differs from `4·protein + 4·carbs + 9·fat` by more than 25%.
6. The result screen shows **per serving and per 100 g side by side**, every additive with its function and a plain explanation, and marks the data *read by AI, not verified*.

If the user first scanned a barcode that was not found and then scans the label, the label is **saved as a product under that barcode** (unverified), so the next person's scan works.

### 1.4 Packaged products are judged on their own data (no category averages)

A packaged product is never scored from what "ghee in general" looks like. Its score comes from that product's own numbers: our product table, then Open Food Facts for that barcode, then the nutrition table on the label. Rules:
- Open Food Facts values that are impossible (macros over 105 g per 100 g, saturated fat above total fat) are dropped, not shown.
- A front-of-pack photo with no readable barcode searches Open Food Facts by brand and name and shows **candidates** (pack size, kcal, saturated fat). The user picks their pack. Listings of the same brand can disagree, so the nutrition-table scan is the exact route.
- With no data at all, there is **no score**.
- Only unpackaged food (idli, dal, roti) is generalised, from the food table, and is labelled an estimate.

### 1.5 Per-serving impact ("daily share")
Every result with a portion shows what one serving uses of the daily limit: energy, saturated fat, sugar, sodium, as a percentage of the user's own targets, or of a 2000 kcal reference day (saturated fat 22 g, sugar 50 g, sodium 2000 mg) when no profile exists. Example: a 15 g ghee serving carries about 11 g saturated fat, about 50% of the reference limit.

### 1.6 Verdict and trust
- **Verdict** (`services/verdict.py`): band + the portion's share of daily limits. excellent → everyday; good → fine; moderate/limit → sometimes/rarely, but "fine in small amounts" if the portion uses 15% or less of every daily limit. A share of 40% or more of one limit is called out. A personal score below 50 can only make the verdict stricter. An allergen match gives "avoid". No score gives "can't judge yet".
- **Trust** (`catalog.trust_level`): verified > community_confirmed (label scans from 2 other users agree within 10% on 3+ nutrients) > from_scan > community (Open Food Facts). A disagreeing scan changes nothing and stays in the scan log for review.

### 1.7 Healthier options
`services/alternatives.py`. For a scored product or dish: take items of the **same family** (ghee with ghee, biscuits with biscuits; products of unknown family get no comparison), keep those scoring at least **10 points higher**, drop any that are allergen-blocked or fit the user's profile below 50, and show the top 3 with the real reason (for example "40% less sugar"). Each shows its trust level. When we hold too few, we pull popular Indian products of that family from Open Food Facts (only entries with sugar, sodium, saturated fat and energy), stored as unverified. With nothing better, the app says so.

### 1.2 Portion arithmetic (food photo)

For each dish: `nutrients = per_100g × grams / 100`, computed for the low and high end of Gemini's gram range. The S / M / L buttons pick low / midpoint / high. The total shown is the sum of the chosen items. Everything is labelled **an estimate**, and dishes under 50% confidence are marked *Not sure, confirm*. The user's corrections are saved against the prediction so accuracy can be measured later.

---

## 2. Quality score (is this food good?)

A transparent weighted score, 0–100. Same for everyone.

```
subscore(metric)  = linear map of the per-100 g value:  "good" threshold → 100,  "bad" threshold → 0
processing        = by NOVA group:  1→100  2→85  3→55  4→20
ingredient_quality= 100 − penalties (additives by concern level, sugar in first three ingredients −15,
                    refined flour first −10, hydrogenated fat −30)
score = Σ(weight × subscore) / Σ(weight of components that HAD data)
```

| Component | Weight | Good → Bad (per 100 g) |
|---|---|---|
| Sugar | 20% | 5 g → 22.5 g |
| Sodium | 15% | 120 mg → 600 mg |
| Saturated fat | 15% | 1.5 g → 5 g |
| Fibre | 15% | 6 g → 0.5 g |
| Protein | 10% | 12 g → 2 g |
| Processing (NOVA) | 10% | group 1 → 4 |
| Ingredient quality | 10% | no flags → penalties |
| Energy density | 5% | 100 → 450 kcal |

**Safety gate (no number without the key facts):** a score is only given if **sugar, sodium and saturated fat** are all known (where they apply to the category). Otherwise the app shows *"No score yet"* plus the range the score could fall in (missing items counted as worst-case and best-case). This stops an ingredient-only label such as ghee's "cow milk fat" from scoring 100.

**Red-flag caps:** if sugar, sodium or saturated fat reaches its "bad" level, the score cannot exceed **59** (one red flag) or **39** (two or more), so one bad nutrient is never averaged away by good ones.

**Drinks:** judged on sugar (good ≤ 2.5 g, bad ≥ 8 g per 100 ml), sodium, processing and ingredients only. Fibre, protein, saturated fat and energy density are skipped.

**Bands:** 80+ excellent · 60–79 good · 40–59 moderate · below 40 limit.

**Category fairness:** fruit isn't penalised for natural sugar, vegetables for low protein, drinks for no fibre or protein. These are skipped for that category, and the reason is shown.

**Confidence:** `data_completeness` = weight of components that had data ÷ weight that applies to the category. 80%+ and verified → high; 60%+ → medium; else low. A product with **no nutrition values at all gets no score**.

**Why this design:** every number in the breakdown can be shown to the user and traced to a source line in the config.

---

## 3. Personal compatibility ("is this good for *me*?")

Separate from the quality score, because "healthy" depends on the person.

```
1. Allergen check        any match in ingredients/allergens      → BLOCKED, overall = 0, red alert
                         "may contain" traces                     → warning
2. Diet preference       vegan/vegetarian/eggetarian vs the food  → alert, excluded from recommendations
3. For each condition the user has (diabetes, hypertension, high cholesterol):
       rule score = Σ(rule weight × linear map of the metric) over that condition's rules
       e.g. diabetes: sugar 40% (5→10 g), carbs 30% (15→60 g), fibre 30% (6→1 g)
            hypertension: sodium 80% (120→600 mg), sat fat 20%
            high cholesterol: sat fat 60%, fibre 40%
4. Goal rule (lose / gain / maintain) scored the same way
5. overall = MIN of all the above   ← the least compatible aspect decides (deliberately conservative)
```

Conditions without rules yet (fatty liver, hyperuricemia, deficiencies…) show a note to follow the doctor's or dietitian's plan. We do not guess rules.

---

## 4. Daily targets

Mifflin–St Jeor, with the numbers in `targets_config.json`:

```
BMR    = 10·kg + 6.25·cm − 5·age + (male +5 | female −161 | other −78)
TDEE   = BMR × activity   (sedentary 1.2 · light 1.375 · moderate 1.55 · active 1.725)
energy = TDEE × goal      (lose ×0.85 · maintain ×1.0 · gain ×1.1),  never below a floor
         floor: male 1500 · female 1200 · other 1350 kcal   (shown to the user when applied)
protein = 0.83 / 1.0 / 1.2 g per kg (maintain / lose / gain)
fat 25% of energy · carbs = the rest · fibre 14 g per 1000 kcal
limits: free sugar ≤ 10% of energy · saturated fat ≤ 10% of energy · sodium ≤ 2000 mg
```

**No targets are calculated** (an explanation is shown instead) when: the profile is incomplete, the user is **under 18**, or the user is **pregnant or breastfeeding**. These need a clinician.

---

## 4b. What we save from scans (for improving the app)

Every scan writes one row: kind, barcode, what the reader extracted, what we showed, and the model used. This lets us measure accuracy and find the most-scanned missing products. **The photo is saved only if the user switches on "Help improve food recognition" in Profile** (off by default), and only up to 1.5 MB. Everything is deleted with the account. `python -m app.tools.export_training` exports the data for training with user ids hashed with a fresh salt, and photos only for opted-in users.

---

## 5. Logging and today

Logging stores the items with their nutrients at that moment. `today = Σ items` in the user's timezone. A nutrient that is missing for any item is flagged *incomplete* rather than silently under-counted. Progress bars compare totals with targets; sugar, sodium and saturated fat turn red above their limit.

---

## 6. Recommendations ("what next?")

Rule-based, no AI.

```
candidates = foods in our table
  drop if: quality score < 55 · allergen match · diet mismatch · compatibility < 50 · one serving > calories left today
gap_fill = 0.6 · min(protein, protein_gap)/protein_gap + 0.4 · min(fibre, fibre_gap)/fibre_gap
utility  = 0.7 · gap_fill + 0.3 · quality/100
→ top N by utility, each with a plain-language reason ("adds 12 g protein toward today's goal")
```

---

## 7. Chat ("Ask")

```
message ─► SAFETY SCREEN ─► emergency / self-harm?  → fixed reply (112), AI NOT called
                         └► otherwise: intent (food? product? "what next"? "how much today?")
                                ─► tools produce VERIFIED FACTS (the engines above)
                                ─► a deterministic draft answer is built from the facts
                                ─► optional: an LLM may only REPHRASE the draft
                                ─► VALIDATOR: reject the rewrite if it adds numbers not in the facts,
                                   a diagnosis, or medication advice → fall back to the draft
```

**Free questions** ("what should I cook tonight?", "tips for my sugar") take the *advice* route: the model gets only de-identified facts (conditions, allergies, diet, goal, age, sex, daily targets, what was eaten today) plus the last six messages, and answers in the user's language under strict rules (no invented nutrient numbers, no diagnosis, no medicine advice, respect allergies). The same validator then checks the reply. If it fails, or the model is unreachable, a deterministic fallback is shown. Emergency, self-harm, eating-disorder, crash-diet and medication messages never reach the model.

If the AI is down or rejected, the user still gets the correct draft.

---

## 8. What happens when things go wrong

| Situation | Behaviour |
|---|---|
| Barcode not in our table or Open Food Facts | "Not found". Suggest scanning the label |
| Open Food Facts entry has no nutrition | Kept, but **no score**; shown as unverified |
| Gemini unavailable or key rejected | Barcode and typed search still work. Photo scan shows the reason, never a fake result |
| Gemini sees a dish we don't have | Name listed, **no numbers** |
| Login expired | App returns to the login screen |
| Server asleep (free hosting) | Short wait message, 90-second limit, retry |

---

## 9. Decisions made, and what is still open

**Decided**
- One scan button. Barcodes auto-detect. The same button handles food and labels, because the server can tell which.
- Open Food Facts is the second source after our own table. It is crowd-sourced, so it is **always labelled unverified**.
- Min-rule for compatibility (the worst aspect wins) and hard block on allergens.
- Targets use Mifflin–St Jeor with conservative floors, and are withheld for under-18s and pregnancy/breastfeeding.
- Asian-Indian BMI cut-offs (18.5 / 23 / 27.5) for the profile screen's BMI hint. It is a hint, not a diagnosis.

**Open: needed before real users**
1. **Clinical review** of every threshold in `scoring_config.json`, `guidelines.json` and `targets_config.json`. Replace the UK front-of-pack bands with FSSAI/ICMR-NIN criteria.
2. **A real Indian food table** (IFCT 2017 plus verified brand data). Today there are about 70 dishes, so many photos end as "not in our food list".
3. **Rules for the other conditions** (fatty liver, uric acid, deficiencies), written by a dietitian.
4. **Check label-table reading accuracy** on real packs (the validation catches inconsistent numbers, but not a confidently wrong, self-consistent reading).
5. **Accuracy measurement** of food-photo predictions from the saved corrections.
6. Security hardening: refresh tokens, rate limiting, password reset, proper database migrations.
