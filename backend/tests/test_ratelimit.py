import pytest
from fastapi import HTTPException

from app.core.ratelimit import RateLimiter
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from tests.conftest import PW

V = "/api/v1"


def test_limiter_blocks_then_recovers(monkeypatch):
    rl = RateLimiter()
    t = [100.0]
    monkeypatch.setattr("app.core.ratelimit.time.monotonic", lambda: t[0])
    for _ in range(3):
        rl.check("k", 3, 60)
    with pytest.raises(HTTPException) as e:
        rl.check("k", 3, 60)
    assert e.value.status_code == 429 and "Retry-After" in e.value.headers
    rl.check("other", 3, 60)   # separate keys are independent
    t[0] += 61
    rl.check("k", 3, 60)       # window passed


def test_login_is_limited_per_ip():
    s = Settings(env="test", database_url="sqlite://", jwt_secret="x" * 40, log_level="WARNING", rate_limit=True)
    c = TestClient(create_app(s))
    codes = [c.post(f"{V}/auth/login", json={"email": "a@b.co", "password": PW}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]


def test_disabled_limiter_does_not_block(client):
    for _ in range(15):
        assert client.post(f"{V}/auth/login", json={"email": "a@b.co", "password": PW}).status_code == 401
