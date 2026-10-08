from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(payload, s.resolved_jwt_secret(), algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    s = get_settings()
    try:
        data = jwt.decode(token, s.resolved_jwt_secret(), algorithms=[s.jwt_algorithm])
        return int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
