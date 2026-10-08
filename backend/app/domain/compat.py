"""Personal compatibility: food + user context + versioned guideline rules -> explained score.

Kept separate from the general food quality score on purpose (master prompt section 15).
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache

from app.core.config import DATA_DIR
from app.domain.scoring import band_label, band_score


@lru_cache
def load_guidelines() -> dict:
    with open(DATA_DIR / "guidelines.json", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class UserContext:
    conditions: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    diet_preference: str | None = None
    goal: str | None = None


@dataclass
class FoodView:
    name: str
    per100g: Mapping[str, float | None]
    allergens: list[str] = field(default_factory=list)
    may_contain: list[str] = field(default_factory=list)
    diet_type: str | None = None  # vegan | vegetarian | eggetarian | non_vegetarian | None (unknown)


_DIET_ALLOWS = {
    "vegan": {"vegan"},
    "vegetarian": {"vegan", "vegetarian"},
    "eggetarian": {"vegan", "vegetarian", "eggetarian"},
    "non_vegetarian": {"vegan", "vegetarian", "eggetarian", "non_vegetarian"},
}


def _rule_set_score(rules: list[dict], per100g: Mapping[str, float | None]) -> tuple[float | None, list[dict]]:
    used, details = [], []
    for r in rules:
        v = per100g.get(r["metric"])
        if v is None:
            continue
        s = band_score(float(v), r["good"], r["bad"])
        used.append((s, r["weight"]))
        lower_better = r["good"] < r["bad"]
        favourable = (v <= r["good"]) if lower_better else (v >= r["good"])
        unfavourable = (v >= r["bad"]) if lower_better else (v <= r["bad"])
        verdict = "favourable" if favourable else "unfavourable" if unfavourable else "middling"
        details.append({"metric": r["metric"], "value": float(v), "unit": r["unit"], "verdict": verdict,
                        "why_it_matters": r["reason"], "source": r["source"]})
    if not used:
        return None, details
    tw = sum(w for _, w in used)
    return sum(s * w for s, w in used) / tw, details


def evaluate_personal(food: FoodView, user: UserContext) -> dict:
    gl = load_guidelines()
    alerts: list[dict] = []
    blocked = False

    for a in user.allergies:
        if a in food.allergens:
            alerts.append({"type": "allergen", "severity": "block",
                           "message": f"Contains {a.replace('_', ' ')}, which you listed as an allergy."})
            blocked = True
        elif a in food.may_contain:
            alerts.append({"type": "allergen_trace", "severity": "warning",
                           "message": f"May contain traces of {a.replace('_', ' ')} (you listed it as an allergy)."})

    if user.diet_preference in _DIET_ALLOWS:
        allowed = _DIET_ALLOWS[user.diet_preference]
        conflict = food.diet_type is not None and food.diet_type not in allowed
        if food.diet_type is None:  # packaged product: infer from declared allergens
            if user.diet_preference in ("vegan",) and ({"milk", "egg", "fish", "shellfish"} & set(food.allergens)):
                conflict = True
            if user.diet_preference in ("vegetarian",) and ({"egg", "fish", "shellfish"} & set(food.allergens)):
                conflict = True
        if conflict:
            alerts.append({"type": "diet_preference", "severity": "info",
                           "message": f"May not match your {user.diet_preference.replace('_', ' ')} preference."})

    cond_results, unsupported = [], []
    for c in user.conditions:
        spec = gl["conditions"].get(c)
        if spec is None:
            unsupported.append(c)
            continue
        score, details = _rule_set_score(spec["rules"], food.per100g)
        cond_results.append({"condition": c, "label": spec["label"],
                             "score": None if score is None else round(score), "details": details})
    if user.goal in gl["goals"]:
        spec = gl["goals"][user.goal]
        score, details = _rule_set_score(spec["rules"], food.per100g)
        cond_results.append({"condition": f"goal:{user.goal}", "label": spec["label"],
                             "score": None if score is None else round(score), "details": details})

    scored = [c["score"] for c in cond_results if c["score"] is not None]
    overall: int | None
    if blocked:
        overall = 0
    elif scored:
        overall = min(scored)  # conservative: the least compatible aspect decides
    else:
        overall = None

    notes = []
    if overall is None and not blocked:
        notes.append("Add health conditions or a goal to your profile to see personalised compatibility.")
    if unsupported:
        notes.append("No nutrition rules yet for: " + ", ".join(unsupported) +
                     ". Please follow guidance from your doctor or dietitian.")
    notes.append("Scores use per-100 g values; portion size matters, so check the per-serving numbers too.")

    return {"overall": overall,
            "label": None if overall is None else ("not suitable - allergen" if blocked else band_label(overall)),
            "blocked": blocked, "alerts": alerts, "conditions": cond_results,
            "unsupported_conditions": unsupported, "notes": notes,
            "guideline_version": gl["version"], "guideline_status": gl["status"],
            "disclaimer": gl["disclaimer"]}
