"""How much of a day's limit does ONE portion use? Makes 'ghee is fine in small amounts' visible in numbers."""
from __future__ import annotations

from app.models import User
from app.services.dashboard import targets_for

# 2000 kcal reference when the user has no targets yet: free sugar and saturated fat at 10% of energy, WHO sodium limit.
_REFERENCE = {"energy_kcal": 2000.0, "sat_fat_g": 22.0, "sugar_g": 50.0, "sodium_mg": 2000.0}
_LABELS = {"energy_kcal": ("Energy", "kcal"), "sat_fat_g": ("Saturated fat", "g"), "sugar_g": ("Sugar", "g"), "sodium_mg": ("Sodium", "mg")}


def daily_share(portion: dict | None, targets: dict | None) -> dict | None:
    if not portion:
        return None
    if targets and targets.get("available"):
        limits = {"energy_kcal": targets["energy_kcal"], "sat_fat_g": targets["sat_fat_g_max"],
                  "sugar_g": targets["sugar_g_max"], "sodium_mg": targets["sodium_mg_max"]}
        basis = "your daily targets"
    else:
        limits, basis = _REFERENCE, "a 2000 kcal reference day (add your profile for personal limits)"
    items = []
    for k, (label, unit) in _LABELS.items():
        v = portion.get(k)
        if v is None or not limits.get(k):
            continue
        items.append({"key": k, "label": label, "amount": round(float(v), 1), "limit": round(float(limits[k]), 1), "unit": unit,
                      "pct": round(100.0 * float(v) / float(limits[k]))})
    return {"basis": basis, "items": items} if items else None


def attach_daily_share(out: dict, user: User) -> dict:
    share = daily_share(out.get("nutrition_for_portion"), targets_for(user))
    if share:
        out["daily_share"] = share
    return out
