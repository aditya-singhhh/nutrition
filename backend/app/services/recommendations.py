"""Rule-based recommendations: foods that close today's protein/fibre gap within the user's constraints.

No LLM involved. The ranking is explainable and every candidate is checked for allergens, diet preference,
condition compatibility and general quality before it is shown.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.compat import FoodView, UserContext, evaluate_personal
from app.domain.scoring import score_food
from app.models import FoodItem, User
from app.services.catalog import nutrition_for, user_context
from app.services.dashboard import today_summary

MIN_QUALITY = 55
MIN_COMPAT = 50


def recommend(db: Session, user: User, limit: int = 5) -> dict:
    ctx: UserContext = user_context(user)
    summary = today_summary(db, user)
    rem = summary["remaining"]
    targets_known = rem is not None
    protein_gap = rem["protein_g"] if targets_known else 25.0
    fiber_gap = rem["fiber_g"] if targets_known else 10.0
    kcal_left = rem["energy_kcal"] if targets_known else None

    items = []
    for f in db.scalars(select(FoodItem)):
        score = score_food(f.nutrients_per_100g, category=f.category, nova=f.nova, verified=f.verified)
        if score["score"] is None or score["score"] < MIN_QUALITY:
            continue
        compat = evaluate_personal(FoodView(f.name, f.nutrients_per_100g, allergens=list(f.allergens),
                                            diet_type=f.diet_type), ctx)
        if compat["blocked"] or any(a["type"] == "diet_preference" for a in compat["alerts"]):
            continue
        if compat["overall"] is not None and compat["overall"] < MIN_COMPAT:
            continue
        serving = nutrition_for(f.nutrients_per_100g, f.serving_g)
        if kcal_left is not None and (serving["energy_kcal"] or 0) > kcal_left:
            continue
        p, fi = serving["protein_g"] or 0.0, serving["fiber_g"] or 0.0
        gap_fill = 0.6 * min(p, protein_gap) / max(protein_gap, 1.0) + 0.4 * min(fi, fiber_gap) / max(fiber_gap, 1.0)
        utility = 0.7 * gap_fill + 0.3 * score["score"] / 100
        reasons = []
        if p >= 0.15 * max(protein_gap, 1.0) and p >= 4:
            reasons.append(f"adds {p:g} g protein toward today's goal")
        if fi >= 2:
            reasons.append(f"adds {fi:g} g fibre")
        if not reasons:
            reasons.append("a balanced choice for your profile")
        items.append({"food": {"id": f.id, "slug": f.slug, "name": f.name},
                      "portion": {"grams": f.serving_g, "label": f.serving_label},
                      "nutrition_for_portion": serving, "quality_score": score["score"],
                      "personal_compatibility": compat["overall"], "reasons": reasons,
                      "data_quality": {"verified": f.verified, "source": f.source}, "_u": utility})
    items.sort(key=lambda x: -x["_u"])
    for i in items:
        i.pop("_u")
    return {"method": "rule_based_v1",
            "based_on": {"protein_gap_g": round(protein_gap, 1), "fibre_gap_g": round(fiber_gap, 1),
                         "calories_left": None if kcal_left is None else round(kcal_left),
                         "targets_available": targets_known},
            "items": items[:limit],
            "disclaimer": "Nutrition guidance only - not medical advice."}
