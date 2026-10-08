"""Pydantic request schemas (response bodies are plain dicts built by deterministic services)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.domain.compat import load_guidelines

Sex = Literal["male", "female", "other"]
Activity = Literal["sedentary", "light", "moderate", "active"]
Goal = Literal["maintain", "lose", "gain"]
DietPref = Literal["vegan", "vegetarian", "eggetarian", "non_vegetarian"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    consent_health_data: bool
    accepted_terms: bool

    @model_validator(mode="after")
    def _need_consent(self):
        if not (self.consent_health_data and self.accepted_terms):
            raise ValueError("consent to health-data processing and acceptance of terms are required")
        return self


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class ProfileIn(BaseModel):
    age: int | None = Field(default=None, ge=1, le=120)
    sex: Sex | None = None
    height_cm: float | None = Field(default=None, ge=50, le=250)
    weight_kg: float | None = Field(default=None, ge=10, le=400)
    activity_level: Activity | None = None
    goal: Goal | None = None
    diet_preference: DietPref | None = None
    region: str | None = Field(default=None, max_length=40)
    timezone: str | None = Field(default=None, max_length=40)
    conditions: list[str] | None = None
    allergies: list[str] | None = None

    @field_validator("conditions")
    @classmethod
    def _conditions(cls, v):
        if v is None:
            return v
        ok = set(load_guidelines()["recognised_conditions"])
        bad = [c for c in v if c not in ok]
        if bad:
            raise ValueError(f"unknown conditions: {bad}; allowed: {sorted(ok)}")
        return sorted(set(v))

    @field_validator("allergies")
    @classmethod
    def _allergies(cls, v):
        if v is None:
            return v
        ok = set(load_guidelines()["valid_allergens"])
        bad = [a for a in v if a not in ok]
        if bad:
            raise ValueError(f"unknown allergens: {bad}; allowed: {sorted(ok)}")
        return sorted(set(v))


class BarcodeIn(BaseModel):
    barcode: str = Field(min_length=8, max_length=20)


class LabelTextIn(BaseModel):
    text: str = Field(min_length=3, max_length=6000)
    nutrients_per_100g: dict[str, float | None] | None = None


class PortionIn(BaseModel):
    grams: float | None = Field(default=None, gt=0, le=5000)
    servings: float | None = Field(default=None, gt=0, le=50)


class AnalyzeIn(PortionIn):
    food_slug: str | None = None
    barcode: str | None = None

    @model_validator(mode="after")
    def _one_target(self):
        if bool(self.food_slug) == bool(self.barcode):
            raise ValueError("provide exactly one of food_slug or barcode")
        return self


class MealItemIn(PortionIn):
    food_slug: str | None = None
    barcode: str | None = None
    grams_min: float | None = Field(default=None, gt=0, le=5000)
    grams_max: float | None = Field(default=None, gt=0, le=5000)
    prediction_id: int | None = None

    @model_validator(mode="after")
    def _validate(self):
        if bool(self.food_slug) == bool(self.barcode):
            raise ValueError("each item needs exactly one of food_slug or barcode")
        if self.grams is None and self.servings is None:
            raise ValueError("each item needs grams or servings")
        return self


class MealIn(BaseModel):
    meal_type: MealType = "snack"
    eaten_at: datetime | None = None
    source: Literal["manual", "photo", "barcode"] = "manual"
    items: list[MealItemIn] = Field(min_length=1, max_length=30)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: int | None = None


class CorrectedItem(BaseModel):
    food_slug: str
    grams: float | None = Field(default=None, gt=0, le=5000)


class FeedbackIn(BaseModel):
    prediction_correct: bool
    corrected_items: list[CorrectedItem] = Field(default_factory=list, max_length=30)
    comment: str | None = Field(default=None, max_length=500)
