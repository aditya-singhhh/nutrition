"""Shareable summary of the last few days of eating, for the person or their doctor/dietitian. Arithmetic only."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import User
from app.services.dashboard import day_bounds_utc, meals_between, targets_for

KEYS = ("energy_kcal", "protein_g", "carbs_g", "sugar_g", "fiber_g", "sodium_mg")
LABEL = {"energy_kcal": "Energy", "protein_g": "Protein", "carbs_g": "Carbohydrate", "sugar_g": "Sugar", "fiber_g": "Fibre", "sodium_mg": "Sodium"}
UNIT = {"energy_kcal": "kcal", "protein_g": "g", "carbs_g": "g", "sugar_g": "g", "fiber_g": "g", "sodium_mg": "mg"}


def build_report(db: Session, user: User, days: int = 7) -> dict:
    days = max(1, min(int(days), 30))
    tz = user.profile.timezone if user.profile else None
    _, end_today, today = day_bounds_utc(tz)
    start = day_bounds_utc(tz, today - timedelta(days=days - 1))[0]
    meals = meals_between(db, user.id, start, end_today)

    per_day: dict = defaultdict(lambda: {k: 0.0 for k in KEYS})
    unknown: dict = defaultdict(set)  # nutrients where some item had no data, so the day's total is a lower bound
    meals_per_day: dict = defaultdict(int)
    items = []
    from zoneinfo import ZoneInfo
    zone = ZoneInfo(tz or "Asia/Kolkata")
    for m in meals:
        d = m.eaten_at.astimezone(zone).date().isoformat() if m.eaten_at.tzinfo else m.eaten_at.date().isoformat()
        meals_per_day[d] += 1
        meal_carbs = 0.0
        for it in m.items:
            for k in KEYS:
                v = (it.nutrients or {}).get(k)
                if v is None:
                    unknown[d].add(k)
                else:
                    per_day[d][k] += float(v)
            c = (it.nutrients or {}).get("carbs_g")
            if c is not None:
                items.append({"name": it.name, "carbs_g": round(float(c), 1), "day": d})
                meal_carbs += float(c)
    logged = sorted(per_day)
    avg = {k: round(sum(per_day[d][k] for d in logged) / len(logged), 1) for k in KEYS} if logged else None
    t = targets_for(user)
    top_carbs = sorted(items, key=lambda x: x["carbs_g"], reverse=True)[:5]
    out = {
        "days": days, "days_logged": len(logged), "meals": sum(meals_per_day.values()),
        "daily": [{"date": d, "meals": meals_per_day[d], **{k: round(per_day[d][k], 1) for k in KEYS},
                   "incomplete": sorted(unknown[d])} for d in logged],
        "average_per_logged_day": avg, "top_carb_items": top_carbs,
        "targets": {k: t[k] for k in ("energy_kcal", "protein_g", "fiber_g", "sugar_g_max", "sodium_mg_max") if t.get("available") and k in t} or None,
        "conditions": sorted(c.condition for c in user.conditions),
    }
    out["text"] = _text(out, user)
    return out


def _text(r: dict, user: User) -> str:
    name = (user.profile.display_name if user.profile and user.profile.display_name else "My")
    lines = [f"{name} food summary - last {r['days']} days", ""]
    if r["conditions"]:
        lines.append("Conditions I told the app about: " + ", ".join(c.replace("_", " ") for c in r["conditions"]))
    if not r["days_logged"]:
        lines.append("No meals were logged in this period.")
        return "\n".join(lines)
    lines.append(f"Logged {r['meals']} meals over {r['days_logged']} of {r['days']} days.")
    lines.append("Average on logged days: " + ", ".join(f"{LABEL[k].lower()} {r['average_per_logged_day'][k]:g} {UNIT[k]}" for k in KEYS) + ".")
    if r["targets"]:
        tg = r["targets"]
        lines.append(f"Daily targets used: about {tg.get('energy_kcal', 0):g} kcal, protein {tg.get('protein_g', 0):g} g, "
                     f"sugar up to {tg.get('sugar_g_max', 0):g} g, sodium up to {tg.get('sodium_mg_max', 0):g} mg.")
    if r["top_carb_items"]:
        lines.append("Highest-carbohydrate items: " + "; ".join(f"{i['name']} ({i['carbs_g']:g} g)" for i in r["top_carb_items"]) + ".")
    if any(d["incomplete"] for d in r["daily"]):
        lines.append("Note: some foods had missing values, so some totals may be lower than the real figure.")
    lines.append("")
    lines.append("Estimates from a nutrition app, not medical advice.")
    return "\n".join(lines)
