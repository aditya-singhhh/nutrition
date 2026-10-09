"""Daily nutrition dashboard: totals, targets, remaining. Deterministic."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.nutrition import NUTRIENT_KEYS, round_nutrients, sum_nutrients
from app.domain.targets import ProfileInput, compute_targets
from app.models import Meal, User


def as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "Asia/Kolkata")
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Kolkata")


def day_bounds_utc(tz_name: str | None, day: date | None = None) -> tuple[datetime, datetime, date]:
    tz = _tz(tz_name)
    d = day or datetime.now(tz).date()
    start = datetime.combine(d, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc), d


def targets_for(user: User) -> dict:
    p = user.profile
    if p is None:
        return {"available": False, "reason": "incomplete_profile",
                "missing_fields": ["age", "sex", "height_cm", "weight_kg", "activity_level"]}
    if p.life_stage in ("pregnant", "breastfeeding"):
        return {"available": False, "reason": "life_stage_review_required",
                "message": "Calorie and nutrient needs change during pregnancy and breastfeeding. Please follow the "
                           "plan from your doctor or dietitian. We won't calculate targets for you."}
    return compute_targets(ProfileInput(p.age, p.sex, p.height_cm, p.weight_kg, p.activity_level, p.goal))


def meals_between(db: Session, user_id: int, start: datetime, end: datetime) -> list[Meal]:
    q = (select(Meal).where(Meal.user_id == user_id, Meal.eaten_at >= start, Meal.eaten_at < end)
         .options(selectinload(Meal.items)).order_by(Meal.eaten_at))
    return list(db.scalars(q))


def today_summary(db: Session, user: User, day: date | None = None) -> dict:
    tz_name = user.profile.timezone if user.profile else None
    start, end, d = day_bounds_utc(tz_name, day)
    meals = meals_between(db, user.id, start, end)
    totals = sum_nutrients(i.nutrients for m in meals for i in m.items)
    t = targets_for(user)

    remaining, exceeded, progress = None, [], None
    if t.get("available"):
        v = totals.values
        remaining = {
            "energy_kcal": max(0.0, t["energy_kcal"] - v["energy_kcal"]),
            "protein_g": max(0.0, t["protein_g"] - v["protein_g"]),
            "carbs_g": max(0.0, t["carbs_g"] - v["carbs_g"]),
            "fat_g": max(0.0, t["fat_g"] - v["fat_g"]),
            "fiber_g": max(0.0, t["fiber_g"] - v["fiber_g"]),
            "sugar_g_before_limit": max(0.0, t["sugar_g_max"] - v["sugar_g"]),
            "sat_fat_g_before_limit": max(0.0, t["sat_fat_g_max"] - v["sat_fat_g"]),
            "sodium_mg_before_limit": max(0.0, t["sodium_mg_max"] - v["sodium_mg"]),
        }
        for key, limit_key, label in (("sugar_g", "sugar_g_max", "sugar"), ("sat_fat_g", "sat_fat_g_max", "saturated fat"),
                                      ("sodium_mg", "sodium_mg_max", "sodium")):
            if v[key] > t[limit_key]:
                exceeded.append({"nutrient": label, "intake": round(v[key], 1), "limit": t[limit_key]})
        progress = {k: round(100 * v[k] / t[tk], 0) for k, tk in
                    (("energy_kcal", "energy_kcal"), ("protein_g", "protein_g"), ("fiber_g", "fiber_g")) if t[tk]}

    return {
        "date": d.isoformat(),
        "totals": round_nutrients(totals.values),
        "incomplete_nutrients": sorted(totals.incomplete & {"energy_kcal", "protein_g", "carbs_g", "fat_g",
                                                            "fiber_g", "sugar_g", "sodium_mg"}),
        "targets": t,
        "remaining": None if remaining is None else round_nutrients(remaining),
        "progress_pct": progress,
        "limits_exceeded": exceeded,
        "meals": [{"id": m.id, "meal_type": m.meal_type, "eaten_at": as_utc(m.eaten_at).isoformat(),
                   "source": m.source,
                   "energy_kcal": round(sum((i.nutrients.get("energy_kcal") or 0) for i in m.items), 1),
                   "items": [{"name": i.name, "grams": i.grams} for i in m.items]} for m in meals],
        "all_nutrient_keys": list(NUTRIENT_KEYS),
    }
