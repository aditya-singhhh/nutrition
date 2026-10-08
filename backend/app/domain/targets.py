"""Daily nutrition targets from profile (Mifflin-St Jeor + configurable guideline values)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import DATA_DIR


@lru_cache
def load_targets_config() -> dict:
    with open(DATA_DIR / "targets_config.json", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class ProfileInput:
    age: int | None
    sex: str | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: str | None
    goal: str | None


def compute_targets(p: ProfileInput) -> dict:
    cfg = load_targets_config()
    missing = [n for n in ("age", "sex", "height_cm", "weight_kg", "activity_level") if getattr(p, n) in (None, "")]
    if missing:
        return {"available": False, "reason": "incomplete_profile", "missing_fields": missing}
    if p.age < cfg["min_adult_age"]:
        return {"available": False, "reason": "paediatric_review_required",
                "message": "Nutrition targets for under-18s should come from a paediatrician or dietitian."}

    sex_const = {"male": 5, "female": -161}.get(p.sex, -78)  # 'other': midpoint
    bmr = 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age + sex_const
    tdee = bmr * cfg["activity_factors"][p.activity_level]
    goal = p.goal if p.goal in cfg["goal_energy_multiplier"] else "maintain"
    energy = tdee * cfg["goal_energy_multiplier"][goal]
    floor = cfg["min_energy_kcal"].get(p.sex, cfg["min_energy_kcal"]["other"])
    floor_applied = energy < floor
    energy = max(energy, floor)

    protein = cfg["protein_g_per_kg"][goal] * p.weight_kg
    fat = cfg["fat_energy_fraction"] * energy / 9
    carbs = max(0.0, (energy - protein * 4 - fat * 9) / 4)
    return {
        "available": True,
        "goal": goal,
        "bmr_kcal": round(bmr),
        "energy_kcal": round(energy),
        "protein_g": round(protein),
        "carbs_g": round(carbs),
        "fat_g": round(fat),
        "fiber_g": round(cfg["fiber_g_per_1000kcal"] * energy / 1000),
        "sugar_g_max": round(cfg["free_sugar_max_energy_fraction"] * energy / 4),
        "sat_fat_g_max": round(cfg["sat_fat_max_energy_fraction"] * energy / 9),
        "sodium_mg_max": cfg["sodium_max_mg"],
        "safety_floor_applied": floor_applied,
        "config_version": cfg["version"],
        "config_status": cfg["status"],
        "sources": cfg["sources"],
    }
