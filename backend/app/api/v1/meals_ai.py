from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.orchestrator import ChatOrchestrator
from app.api.deps import current_user, get_db, get_gateway
from app.domain.barcode import InvalidBarcode, normalize_barcode
from app.domain.nutrition import round_nutrients, scale_nutrients, sum_nutrients
from app.models import Meal, MealItem, ModelPrediction, PredictionFeedback, User
from app.schemas import ChatIn, FeedbackIn, MealIn
from app.services import catalog
from app.services.audit import audit
from app.services.dashboard import _tz, as_utc, day_bounds_utc, meals_between, today_summary
from app.services.recommendations import recommend

router = APIRouter()


def _meal_payload(m: Meal) -> dict:
    totals = sum_nutrients(i.nutrients for i in m.items)
    return {"id": m.id, "meal_type": m.meal_type, "eaten_at": as_utc(m.eaten_at).isoformat(), "source": m.source,
            "items": [{"id": i.id, "name": i.name, "grams": i.grams, "grams_min": i.grams_min, "grams_max": i.grams_max,
                       "nutrients": round_nutrients(i.nutrients)} for i in m.items],
            "totals": round_nutrients(totals.values), "incomplete_nutrients": sorted(totals.incomplete)}


@router.post("/meals", status_code=201, tags=["meals"])
def create_meal(body: MealIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    eaten = body.eaten_at or datetime.now(timezone.utc)
    if eaten.tzinfo is None:  # naive timestamps are interpreted in the user's own timezone
        eaten = eaten.replace(tzinfo=_tz(user.profile.timezone if user.profile else None))
    eaten = eaten.astimezone(timezone.utc)

    meal = Meal(user_id=user.id, eaten_at=eaten, meal_type=body.meal_type, source=body.source)
    for it in body.items:
        food = prod = None
        if it.food_slug:
            food = catalog.get_food_by_slug(db, it.food_slug)
            if food is None:
                raise HTTPException(404, f"food not found: {it.food_slug}")
            per100, serving, name = food.nutrients_per_100g, food.serving_g, food.name
        else:
            try:
                code = normalize_barcode(it.barcode or "")
            except InvalidBarcode as e:
                raise HTTPException(422, str(e)) from None
            prod = catalog.get_product(db, code)
            if prod is None:
                raise HTTPException(404, f"product not found: {code}")
            per100, serving, name = prod.nutrients_per_100g, prod.serving_g or 100.0, f"{prod.brand} {prod.name}"
        grams = it.grams if it.grams is not None else it.servings * serving
        if it.grams_min is not None and it.grams_max is not None and not (it.grams_min <= grams <= it.grams_max):
            raise HTTPException(422, "grams must lie within grams_min..grams_max")
        if it.prediction_id is not None:
            pred = db.get(ModelPrediction, it.prediction_id)
            if pred is None or pred.user_id != user.id:
                raise HTTPException(404, "prediction not found")
        meal.items.append(MealItem(
            food_id=food.id if food else None, product_id=prod.id if prod else None, name=name, grams=grams,
            grams_min=it.grams_min, grams_max=it.grams_max, prediction_id=it.prediction_id,
            nutrients=round_nutrients(scale_nutrients(per100, grams), 2)))
    db.add(meal)
    db.commit()
    audit(db, user.id, "create_meal", "meal", meal.id)
    return _meal_payload(meal)


@router.get("/meals", tags=["meals"])
def list_meals(day: date | None = Query(None, alias="date"), user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    start, end, d = day_bounds_utc(user.profile.timezone if user.profile else None, day)
    return {"date": d.isoformat(), "meals": [_meal_payload(m) for m in meals_between(db, user.id, start, end)]}


@router.delete("/meals/{meal_id}", status_code=204, tags=["meals"])
def delete_meal(meal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    meal = db.scalar(select(Meal).where(Meal.id == meal_id, Meal.user_id == user.id))
    if meal is None:
        raise HTTPException(404, "meal not found")
    db.delete(meal)
    db.commit()
    audit(db, user.id, "delete_meal", "meal", meal_id)


@router.get("/nutrition/today", tags=["nutrition"])
def nutrition_today(day: date | None = Query(None, alias="date"), user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    return today_summary(db, user, day)


# ------------------------------------------------------------------ AI
@router.post("/chat", tags=["ai"])
def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db), gw=Depends(get_gateway)):
    turn = ChatOrchestrator(gw).handle(db, user, body.message, body.session_id)
    return {"reply": turn.reply, "session_id": turn.session_id, "intent": turn.intent,
            "tools_used": turn.tools_used, "safety_level": turn.safety_level,
            "prediction_id": turn.prediction_id}


@router.get("/recommendations", tags=["ai"])
def recommendations(limit: int = Query(5, ge=1, le=10), user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    return recommend(db, user, limit)


@router.post("/predictions/{prediction_id}/feedback", status_code=201, tags=["ai"])
def prediction_feedback(prediction_id: int, body: FeedbackIn, user: User = Depends(current_user),
                        db: Session = Depends(get_db)):
    """Data flywheel: corrections to a prediction are stored with the prediction they refer to."""
    pred = db.get(ModelPrediction, prediction_id)
    if pred is None or pred.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "prediction not found")
    for ci in body.corrected_items:
        if catalog.get_food_by_slug(db, ci.food_slug) is None:
            raise HTTPException(422, f"unknown food in correction: {ci.food_slug}")
    fb = PredictionFeedback(prediction_id=pred.id, user_id=user.id, correction=body.model_dump())
    db.add(fb)
    db.commit()
    return {"id": fb.id, "prediction_id": pred.id}
