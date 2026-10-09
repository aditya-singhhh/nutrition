import os

os.environ["HC_ENV"] = "test"
os.environ["HC_OFF_LOOKUP"] = "false"
os.environ["HC_JWT_SECRET"] = "test-secret-" + "x" * 32

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.ai.providers import AIGateway, MockOCRProvider, MockVisionProvider  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402

get_settings.cache_clear()

PW = "correct-horse-battery"


def make_client(gateway: AIGateway | None = None) -> TestClient:
    s = Settings(env="test", database_url="sqlite://", jwt_secret=os.environ["HC_JWT_SECRET"], log_level="WARNING")
    return TestClient(create_app(s, gateway))


def register(client: TestClient, email="user@example.com") -> dict:
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": PW, "consent_health_data": True, "accepted_terms": True})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


FULL_PROFILE = {"age": 30, "sex": "male", "height_cm": 175, "weight_kg": 75, "activity_level": "moderate",
                "goal": "maintain", "diet_preference": "vegetarian"}


@pytest.fixture
def client():
    return make_client()


@pytest.fixture
def auth(client):
    return register(client)


@pytest.fixture
def ai_client():
    """Client whose gateway has mock vision + OCR providers."""
    from app.ai.providers import DishCandidate
    gw = AIGateway(vision=MockVisionProvider([
        DishCandidate("masala-dosa", 0.91, 120, 180),
        DishCandidate("sambar", 0.42, 100, 150),
        DishCandidate("made-up-dish", 0.8, 100, 100),
    ]), ocr=MockOCRProvider("Ingredients: Wheat flour (60%), sugar, palm oil, emulsifier (INS 322), colour (INS 102). May contain traces of peanut."))
    return make_client(gw)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.models import Base
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as s:
        yield s
