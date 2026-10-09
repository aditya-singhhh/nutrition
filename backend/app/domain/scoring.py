"""Transparent 0-100 food quality score. Every point is traceable to a component, a weight and a source."""
from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache

from app.core.config import DATA_DIR


@lru_cache
def load_scoring_config() -> dict:
    with open(DATA_DIR / "scoring_config.json", encoding="utf-8") as f:
        return json.load(f)


def band_score(value: float, good: float, bad: float) -> float:
    """100 at `good`, 0 at `bad`, linear between, clipped. Works for 'lower is better' and 'higher is better'."""
    if good == bad:
        raise ValueError("good and bad thresholds must differ")
    t = (value - bad) / (good - bad)
    return 100.0 * max(0.0, min(1.0, t))


def band_label(score: float, cfg: dict | None = None) -> str:
    cfg = cfg or load_scoring_config()
    for floor, label in cfg["bands"]:
        if score >= floor:
            return label
    return cfg["bands"][-1][1]


def _describe(value: float, good: float, bad: float, unit: str) -> str:
    lower_better = good < bad
    if (lower_better and value <= good) or (not lower_better and value >= good):
        return f"{value:g} {unit} is in the favourable range"
    if (lower_better and value >= bad) or (not lower_better and value <= bad):
        return f"{value:g} {unit} is in the unfavourable range"
    return f"{value:g} {unit} is in the middle range"


REQUIRED_FOR_SCORE = ("sugar", "sodium", "sat_fat")


def score_food(
    per100g: Mapping[str, float | None],
    *,
    category: str | None = None,
    nova: int | None = None,
    additives: list[dict] | None = None,
    ingredient_flags: list[dict] | None = None,
    ingredients_known: bool = False,
    verified: bool = False,
    weights_override: Mapping[str, float] | None = None,
) -> dict:
    """General food quality score.

    Components with missing data are excluded and the remaining weights are renormalised - the result
    says which were excluded and lowers `confidence`, rather than silently treating unknowns as zero.
    """
    cfg = load_scoring_config()
    weights = dict(cfg["weights"])
    if weights_override:
        weights.update(weights_override)
    override = cfg["category_overrides"].get(category or "", {})
    excluded_by_category = set(override.get("exclude", []))

    comps: list[dict] = []
    excluded: list[dict] = []

    def exclude(key: str, label: str, why: str) -> None:
        excluded.append({"key": key, "label": label, "reason": why})

    for key, spec in cfg["components"].items():
        if key in excluded_by_category:
            exclude(key, spec["label"], override.get("why", "not applicable to this category"))
            continue
        value = per100g.get(spec["metric"])
        if value is None:
            exclude(key, spec["label"], "no data available")
            continue
        spec = {**spec, **cfg.get("category_thresholds", {}).get(category or "", {}).get(key, {})}
        sub = band_score(float(value), spec["good"], spec["bad"])
        comps.append({"key": key, "label": spec["label"], "value": float(value), "unit": spec["unit"],
                      "subscore": round(sub, 1), "weight": weights[key],
                      "explanation": _describe(float(value), spec["good"], spec["bad"], spec["unit"]),
                      "source": spec["source"]})

    if "processing" in excluded_by_category:
        exclude("processing", "Processing", override.get("why", "not applicable to this category"))
    elif nova is None:
        exclude("processing", "Processing", "processing level unknown")
    else:
        sub = float(cfg["processing_scores"][str(nova)])
        comps.append({"key": "processing", "label": "Processing", "value": nova, "unit": "NOVA group",
                      "subscore": sub, "weight": weights["processing"],
                      "explanation": f"NOVA group {nova} (1 = unprocessed, 4 = ultra-processed)",
                      "source": "NOVA classification (Monteiro et al.)"})

    if "ingredient_quality" in excluded_by_category:
        exclude("ingredient_quality", "Ingredient quality", override.get("why", "not applicable to this category"))
    elif not ingredients_known:
        exclude("ingredient_quality", "Ingredient quality", "ingredient list not available")
    else:
        penalty = 0.0
        notes = []
        for a in additives or []:
            p = cfg["additive_penalties"].get(a["category"], 0)
            if p:
                penalty += p
                notes.append(f"INS {a['ins']} {a['name']} ({a['category'].replace('_', ' ')}): -{p}")
        for fl in ingredient_flags or []:
            p = cfg["ingredient_flag_penalties"].get(fl["code"], 0)
            if p:
                penalty += p
                notes.append(f"{fl['code'].replace('_', ' ')}: -{p}")
        sub = max(0.0, 100.0 - penalty)
        comps.append({"key": "ingredient_quality", "label": "Ingredient quality", "value": round(penalty, 1),
                      "unit": "penalty points", "subscore": sub, "weight": weights["ingredient_quality"],
                      "explanation": "; ".join(notes) if notes else "no flagged additives or ingredients",
                      "source": "Additive reference list (see evidence_source per additive)"})

    # Safety gate: a handful of components must never stand in for a whole food. Sugar, sodium and saturated fat are the
    # three nutrients that most often make a food a poor choice, so without all of them (where they apply) we give a
    # RANGE, not a number. (Without this, an ingredient-only label such as ghee's "cow milk fat" scored 100.)
    present = {c["key"] for c in comps}
    required = [k for k in REQUIRED_FOR_SCORE if k not in excluded_by_category]
    missing_required = [k for k in required if k not in present]
    if missing_required:
        applicable = sum(w for k, w in weights.items() if k not in excluded_by_category)
        got = sum(c["subscore"] * c["weight"] for c in comps)
        lost = sum(w for k, w in weights.items() if k not in excluded_by_category and k not in present)
        labels = [cfg["components"][k]["label"].lower() for k in missing_required]
        return {"score": None, "band": None, "components": comps, "excluded": excluded, "confidence": "none",
                "score_range": {"min": round(got / applicable), "max": round((got + 100 * lost) / applicable)} if applicable else None,
                "missing_required": missing_required, "config_version": cfg["version"], "config_status": cfg["status"],
                "summary": f"Not enough data for a score. Still needed: {', '.join(labels)}. Scan the nutrition table to complete it."}

    total_weight = sum(c["weight"] for c in comps)
    if total_weight <= 0:
        return {"score": None, "band": None, "components": [], "excluded": excluded, "confidence": "none",
                "config_version": cfg["version"], "config_status": cfg["status"],
                "summary": "Not enough data to score this food."}

    score = sum(c["subscore"] * c["weight"] for c in comps) / total_weight
    caps = cfg.get("red_flag_caps")
    reds = [c for c in comps if c["key"] in REQUIRED_FOR_SCORE and c["subscore"] <= 0.0]
    cap_note = None
    if caps and reds:
        cap = caps["two_or_more"] if len(reds) >= 2 else caps["one"]
        if score > cap:
            score = float(cap)
            cap_note = "Score capped because " + " and ".join(c["label"].lower() for c in reds) + (" is" if len(reds) == 1 else " are") + " at a high level."
    for c in comps:
        c["effective_weight"] = round(c["weight"] / total_weight, 3)
        c["points"] = round(c["subscore"] * c["weight"] / total_weight, 1)

    # completeness = share of the *applicable* weight (category-appropriate components) that had data
    applicable_weight = sum(w for k, w in weights.items() if k not in excluded_by_category)
    completeness = total_weight / applicable_weight if applicable_weight else 0.0
    if completeness >= 0.8 and verified:
        confidence = "high"
    elif completeness >= 0.6:
        confidence = "medium"
    else:
        confidence = "low"

    weakest = min(comps, key=lambda c: c["subscore"])
    strongest = max(comps, key=lambda c: c["subscore"])
    summary = f"Strongest: {strongest['label'].lower()}. Weakest: {weakest['label'].lower()}."
    if cap_note:
        summary = cap_note + " " + summary
    return {"score": round(score), "band": band_label(score, cfg), "components": comps, "excluded": excluded,
            "confidence": confidence, "data_completeness": round(completeness, 2), "summary": summary, "capped": cap_note is not None,
            "config_version": cfg["version"], "config_status": cfg["status"]}
