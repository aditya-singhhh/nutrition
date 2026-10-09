"""Plain-language verdict and household measures. Pure arithmetic and fixed rules, no AI.

Why: a bare '54/100' does not tell a shopper what to DO. The verdict turns the score plus the portion into one calm sentence
code (the app renders it in English or Hindi), and the household measures use units people actually cook with.
"""
from __future__ import annotations

SUGAR_G_PER_TSP = 4.0     # level teaspoon of sugar
SALT_G_PER_TSP = 5.0      # level teaspoon of salt (ICMR/WHO "under 5 g salt a day" is about one teaspoon)
FAT_G_PER_TSP = 5.0       # teaspoon of ghee or oil
SODIUM_MG_PER_G_SALT = 400.0

SMALL_SHARE = 15   # a portion that uses at most this % of every daily limit counts as "small"
HEAVY_SHARE = 40   # a portion that uses this % or more of any one limit is flagged


def household(portion: dict | None) -> dict | None:
    if not portion:
        return None
    out = {}
    if portion.get("sugar_g") is not None:
        out["sugar_tsp"] = round(portion["sugar_g"] / SUGAR_G_PER_TSP, 1)
    if portion.get("sodium_mg") is not None:
        out["salt_tsp"] = round(portion["sodium_mg"] / SODIUM_MG_PER_G_SALT / SALT_G_PER_TSP, 2)
    if portion.get("fat_g") is not None:
        out["fat_tsp"] = round(portion["fat_g"] / FAT_G_PER_TSP, 1)
    return out or None


def verdict(out: dict) -> dict:
    """Return {code, tone, reasons[{code, value}]} for a result dict (food or product)."""
    q = out.get("quality_score") or {}
    pc = out.get("personal_compatibility") or {}
    share = {i["key"]: i["pct"] for i in (out.get("daily_share") or {}).get("items", [])}
    watch = [share[k] for k in ("sat_fat_g", "sugar_g", "sodium_mg") if k in share]
    reasons: list[dict] = []

    for k, code in (("sat_fat_g", "high_sat_fat"), ("sugar_g", "high_sugar"), ("sodium_mg", "high_sodium")):
        if share.get(k, 0) >= HEAVY_SHARE:
            reasons.append({"code": code, "value": share[k]})

    if pc.get("blocked"):
        return {"code": "avoid", "tone": "bad", "reasons": [{"code": "allergen", "value": None}]}

    band = (q.get("band") or "").lower()
    if q.get("score") is None:
        return {"code": "unknown", "tone": "neutral", "reasons": reasons}

    code = {"excellent": "everyday", "good": "fine", "moderate": "sometimes"}.get(band, "rarely")
    if code in ("sometimes", "rarely") and watch and max(watch) <= SMALL_SHARE:
        code = "small_ok"          # not a great food, but this portion barely dents the day
    tone = {"everyday": "ok", "fine": "ok", "small_ok": "ok", "sometimes": "warn", "rarely": "warn"}[code]

    overall = pc.get("overall")
    if overall is not None and overall < 50:
        # the personal result can only make the verdict MORE cautious, never less
        reasons.append({"code": "not_ideal_for_you", "value": overall})
        if code in ("everyday", "fine"):
            code, tone = "sometimes", "warn"
    return {"code": code, "tone": tone, "reasons": reasons}


def attach_verdict(out: dict) -> dict:
    out["verdict"] = verdict(out)
    h = household(out.get("nutrition_for_portion"))
    if h:
        out["household"] = h
    return out
