"""Turn a nutrition table read off a pack (by OCR/AI) into trustworthy per-100 g values, or refuse.

The reader is not trusted: every number is range-checked and cross-checked against the others (energy must roughly equal
4*protein + 4*carbs + 9*fat; saturated fat cannot exceed fat; sugars cannot exceed carbohydrate). Anything that doesn't add
up is dropped and reported, never silently kept.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

KEYS = ("energy_kcal", "protein_g", "carbs_g", "sugar_g", "fat_g", "sat_fat_g", "fiber_g", "sodium_mg")
_MAX = {"energy_kcal": 950.0, "protein_g": 100.0, "carbs_g": 100.0, "sugar_g": 100.0, "fat_g": 100.0, "sat_fat_g": 100.0,
        "fiber_g": 100.0, "sodium_mg": 40000.0}
SALT_TO_SODIUM_MG_PER_G = 400.0  # 1 g salt = 400 mg sodium


@dataclass
class LabelNutrition:
    basis: str = "none"  # per_100g | scaled_from_serving | none
    serving_g: float | None = None
    per_100g: dict = field(default_factory=dict)
    per_serving: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _clean(raw: object) -> dict:
    out: dict[str, float] = {}
    if not isinstance(raw, dict):
        return out
    vals = dict(raw)
    if vals.get("sodium_mg") is None and vals.get("salt_g") is not None:
        try:
            vals["sodium_mg"] = float(vals["salt_g"]) * SALT_TO_SODIUM_MG_PER_G
        except (TypeError, ValueError):
            pass
    for k in KEYS:
        v = vals.get(k)
        if v is None or isinstance(v, bool):
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f) and 0 <= f <= _MAX[k]:
            out[k] = round(f, 2)
    return out


def _consistent(n: dict, warnings: list[str]) -> dict:
    n = dict(n)
    if "sat_fat_g" in n and "fat_g" in n and n["sat_fat_g"] > n["fat_g"] + 0.5:
        warnings.append("Saturated fat was higher than total fat, so it was ignored. Check the pack.")
        del n["sat_fat_g"]
    if "sugar_g" in n and "carbs_g" in n and n["sugar_g"] > n["carbs_g"] + 0.5:
        warnings.append("Sugar was higher than total carbohydrate, so it was ignored. Check the pack.")
        del n["sugar_g"]
    return n


def parse_label_nutrition(raw: dict | None) -> LabelNutrition:
    res = LabelNutrition()
    if not isinstance(raw, dict):
        return res
    try:
        sg = float(raw.get("serving_g")) if raw.get("serving_g") is not None else None
    except (TypeError, ValueError):
        sg = None
    res.serving_g = sg if sg and 0 < sg <= 2000 else None
    p100, pserv = _clean(raw.get("per_100g")), _clean(raw.get("per_serving"))

    if len(p100) >= 4:
        res.basis, base = "per_100g", p100
    elif len(pserv) >= 4 and res.serving_g:
        base = {k: round(v * 100.0 / res.serving_g, 2) for k, v in pserv.items()}
        res.basis = "scaled_from_serving"
        res.warnings.append(f"Only per-serving values were readable, so they were scaled from the {res.serving_g:g} g serving.")
    else:
        if p100 or pserv:
            res.warnings.append("The nutrition table was only partly readable. Scan it again, closer and in good light.")
        return res

    # sanity: macros per 100 g cannot exceed 100 g together
    macros = base.get("protein_g", 0) + base.get("carbs_g", 0) + base.get("fat_g", 0)
    if macros > 105:
        res.warnings.append("The numbers don't add up (more than 100 g of nutrients per 100 g). They were discarded.")
        res.basis = "none"
        return res
    base = _consistent(base, res.warnings)
    if all(k in base for k in ("energy_kcal", "protein_g", "carbs_g", "fat_g")) and base["energy_kcal"] > 20:
        expected = 4 * base["protein_g"] + 4 * base["carbs_g"] + 9 * base["fat_g"]
        if abs(base["energy_kcal"] - expected) / base["energy_kcal"] > 0.25:
            res.warnings.append(f"Energy ({base['energy_kcal']:g} kcal) doesn't match fat, carbs and protein (about {expected:g} kcal). "
                                "The reading may be wrong. Please check the pack.")
    res.per_100g = base
    s = res.serving_g
    res.per_serving = pserv if (pserv and res.basis == "per_100g") else (
        {k: round(v * s / 100.0, 2) for k, v in base.items()} if s else {})
    return res
