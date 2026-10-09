from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.providers import AIGateway
from app.core.security import decode_access_token
from app.models import User

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def get_gateway(request: Request) -> AIGateway:
    return request.app.state.gateway


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing credentials",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    uid = decode_access_token(creds.credentials)
    if uid is None:
        raise unauthorized
    user = db.scalar(select(User).where(User.id == uid).options(
        selectinload(User.profile), selectinload(User.conditions), selectinload(User.allergies)))
    if user is None:
        raise unauthorized
    return user


_MAGIC = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"))


def read_image(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an uploaded image with a hard size cap and magic-byte check (don't trust the client's content-type)."""
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "image too large")
    ok = any(data.startswith(m) for m, _ in _MAGIC) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    if not ok:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "only JPEG, PNG or WebP images are accepted")
    return data


def decode_image_b64(b64: str, max_bytes: int) -> bytes:
    import base64
    import binascii

    if "," in b64[:40]:  # tolerate a data: URI prefix
        b64 = b64.split(",", 1)[1]
    try:
        data = base64.b64decode(b64, validate=False)
    except (binascii.Error, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "image is not valid base64") from None
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "image too large")
    if not (any(data.startswith(m) for m, _ in _MAGIC) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "only JPEG, PNG or WebP images are accepted")
    return data
