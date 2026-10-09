from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Allergy, ModelPrediction, PredictionFeedback, ScanRecord, User, UserCondition, UserProfile
from app.schemas import LoginIn, ProfileIn, RegisterIn
from app.services.audit import audit
from app.services.dashboard import targets_for

router = APIRouter()

# Compared against when the email is unknown so login timing doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("not-a-real-password")


def _user_payload(u: User) -> dict:
    p = u.profile
    return {
        "id": u.id, "email": u.email, "consent_version": u.consent_version,
        "profile": None if p is None else {
            "age": p.age, "sex": p.sex, "height_cm": p.height_cm, "weight_kg": p.weight_kg,
            "activity_level": p.activity_level, "goal": p.goal, "diet_preference": p.diet_preference,
            "region": p.region, "display_name": p.display_name, "target_weight_kg": p.target_weight_kg,
            "life_stage": p.life_stage, "training_opt_in": bool(p.training_opt_in), "country": p.country, "locale": p.locale, "timezone": p.timezone},
        "conditions": sorted(c.condition for c in u.conditions),
        "allergies": sorted(a.allergen for a in u.allergies),
    }


@router.post("/auth/register", status_code=201, tags=["auth"])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    s = get_settings()
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), consent_version=s.consent_version)
    user.profile = UserProfile()
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "an account with this email already exists") from None
    audit(db, user.id, "register", "user", user.id)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.post("/auth/login", tags=["auth"])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        audit(db, user.id if user else None, "login_failed", "user", user.id if user else None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect email or password")
    audit(db, user.id, "login", "user", user.id)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/users/me", tags=["users"])
def me(user: User = Depends(current_user)):
    return _user_payload(user)


@router.put("/users/me/profile", tags=["users"])
def update_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    conditions, allergies = data.pop("conditions", None), data.pop("allergies", None)
    if user.profile is None:
        user.profile = UserProfile()
    for k, v in data.items():
        setattr(user.profile, k, v)
    if conditions is not None:
        user.conditions = [UserCondition(condition=c) for c in conditions]
    if allergies is not None:
        user.allergies = [Allergy(allergen=a) for a in allergies]
    db.commit()
    audit(db, user.id, "update_profile", "user", user.id)  # field names/values deliberately not logged
    return _user_payload(user)


@router.get("/users/me/targets", tags=["users"])
def my_targets(user: User = Depends(current_user)):
    return targets_for(user)


@router.delete("/users/me", status_code=204, tags=["users"])
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Right-to-erasure: removes the account, profile, meals, chats, predictions and feedback."""
    uid = user.id
    pred_ids = list(db.scalars(select(ModelPrediction.id).where(ModelPrediction.user_id == uid)))
    db.execute(delete(ScanRecord).where(ScanRecord.user_id == uid))  # includes any stored photos
    db.delete(user)  # ORM cascades: profile, conditions, allergies, meals(+items), chat sessions(+messages)
    db.flush()
    if pred_ids:
        db.execute(delete(PredictionFeedback).where(PredictionFeedback.prediction_id.in_(pred_ids)))
        db.execute(delete(ModelPrediction).where(ModelPrediction.id.in_(pred_ids)))
    db.commit()
    audit(db, uid, "delete_account", "user", uid)
