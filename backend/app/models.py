"""SQLAlchemy models (MVP subset of the full schema in the master prompt).

Nutrient dicts use the canonical keys in app.domain.nutrition.NUTRIENT_KEYS, per 100 g.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="user")
    consent_version: Mapped[str] = mapped_column(String(40))
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    conditions: Mapped[list[UserCondition]] = relationship(cascade="all, delete-orphan")
    allergies: Mapped[list[Allergy]] = relationship(cascade="all, delete-orphan")
    meals: Mapped[list[Meal]] = relationship(cascade="all, delete-orphan")
    chat_sessions: Mapped[list[ChatSession]] = relationship(cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    country: Mapped[str] = mapped_column(String(2), default="IN")
    locale: Mapped[str] = mapped_column(String(10), default="en-IN")
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Kolkata")
    age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(10))  # male | female | other
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    activity_level: Mapped[str | None] = mapped_column(String(20))
    goal: Mapped[str | None] = mapped_column(String(20))  # maintain | lose | gain
    diet_preference: Mapped[str | None] = mapped_column(String(20))  # vegan|vegetarian|eggetarian|non_vegetarian
    region: Mapped[str | None] = mapped_column(String(40))
    display_name: Mapped[str | None] = mapped_column(String(60))
    target_weight_kg: Mapped[float | None] = mapped_column(Float)
    life_stage: Mapped[str | None] = mapped_column(String(20))  # pregnant | breastfeeding | None
    training_opt_in: Mapped[bool | None] = mapped_column(Boolean, default=False)  # may we keep scan PHOTOS to improve recognition
    user: Mapped[User] = relationship(back_populates="profile")


class UserCondition(Base):
    __tablename__ = "user_conditions"
    __table_args__ = (UniqueConstraint("user_id", "condition"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    condition: Mapped[str] = mapped_column(String(40))


class Allergy(Base):
    __tablename__ = "allergies"
    __table_args__ = (UniqueConstraint("user_id", "allergen"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    allergen: Mapped[str] = mapped_column(String(40))


class FoodItem(Base):
    __tablename__ = "food_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[list] = mapped_column(JsonType, default=list)
    region: Mapped[str | None] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(40))
    diet_type: Mapped[str] = mapped_column(String(20))  # vegan | vegetarian | eggetarian | non_vegetarian
    allergens: Mapped[list] = mapped_column(JsonType, default=list)
    nova: Mapped[int | None] = mapped_column(Integer)
    serving_g: Mapped[float] = mapped_column(Float)
    serving_label: Mapped[str] = mapped_column(String(60))
    nutrients_per_100g: Mapped[dict] = mapped_column(JsonType)
    source: Mapped[str] = mapped_column(String(60))
    confidence: Mapped[str] = mapped_column(String(40))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[str] = mapped_column(String(2), default="IN")


class PackagedProduct(Base):
    __tablename__ = "packaged_products"
    id: Mapped[int] = mapped_column(primary_key=True)
    barcode: Mapped[str] = mapped_column(String(14), unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))
    serving_g: Mapped[float | None] = mapped_column(Float)
    nutrients_per_100g: Mapped[dict] = mapped_column(JsonType)
    ingredients_text: Mapped[str | None] = mapped_column(Text)
    allergens: Mapped[list] = mapped_column(JsonType, default=list)
    additives: Mapped[list] = mapped_column(JsonType, default=list)  # list of INS codes
    nova: Mapped[int | None] = mapped_column(Integer)
    country: Mapped[str] = mapped_column(String(2), default="IN")
    source: Mapped[str] = mapped_column(String(60))
    confidence: Mapped[str] = mapped_column(String(40))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmations: Mapped[int | None] = mapped_column(Integer, default=0)  # independent label scans that agree with the stored values


class Meal(Base):
    __tablename__ = "meals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    meal_type: Mapped[str] = mapped_column(String(20), default="snack")
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | photo | barcode
    items: Mapped[list[MealItem]] = relationship(cascade="all, delete-orphan")


class MealItem(Base):
    __tablename__ = "meal_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[int | None] = mapped_column(ForeignKey("food_items.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("packaged_products.id"))
    name: Mapped[str] = mapped_column(String(160))
    grams: Mapped[float] = mapped_column(Float)
    grams_min: Mapped[float | None] = mapped_column(Float)
    grams_max: Mapped[float | None] = mapped_column(Float)
    # Snapshot of computed totals so history stays stable if reference data is corrected later.
    nutrients: Mapped[dict] = mapped_column(JsonType)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("model_predictions.id"))


class ModelPrediction(Base):
    """Traceability record for every AI/ML output (master prompt section 5)."""

    __tablename__ = "model_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # food_photo | label_ocr | chat
    model_name: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    confidence: Mapped[float | None] = mapped_column(Float)
    input_type: Mapped[str] = mapped_column(String(30))
    input_digest: Mapped[str | None] = mapped_column(String(64))  # sha256 only; raw input not stored
    output: Mapped[dict] = mapped_column(JsonType)
    source: Mapped[str] = mapped_column(String(40), default="live")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PredictionFeedback(Base):
    __tablename__ = "prediction_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("model_predictions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    correction: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Access/mutation trail. Never store health values or free text here - ids and actions only."""

    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)  # intentionally no FK: survives deletion
    action: Mapped[str] = mapped_column(String(60))
    resource: Mapped[str | None] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    messages: Mapped[list[ChatMessage]] = relationship(cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    safety_level: Mapped[str | None] = mapped_column(String(20))
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("model_predictions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScanRecord(Base):
    """Every scan, kept so recognition can be improved and audited. The photo itself is stored ONLY if the user opted in."""
    __tablename__ = "scan_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(20))  # barcode | food | label | product
    barcode: Mapped[str | None] = mapped_column(String(14), index=True)
    model_name: Mapped[str | None] = mapped_column(String(60))
    prediction_id: Mapped[int | None] = mapped_column(Integer)
    extracted: Mapped[dict] = mapped_column(JsonType, default=dict)  # what the reader/model produced
    outcome: Mapped[dict] = mapped_column(JsonType, default=dict)  # what we showed (slugs, score, warnings)
    image: Mapped[bytes | None] = mapped_column(LargeBinary)  # only with opt-in
    image_sha256: Mapped[str | None] = mapped_column(String(64))
    correction: Mapped[dict | None] = mapped_column(JsonType)  # user's fix, when given
