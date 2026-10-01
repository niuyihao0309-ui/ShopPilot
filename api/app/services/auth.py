import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings, get_settings
from app.models import User, UserStatus


class AuthTokenError(ValueError):
    pass


def create_access_token(user: User, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "exp": int(expires_at.timestamp()),
    }
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{encoded_payload}.{_sign(encoded_payload, settings.auth_secret_key)}"


def parse_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthTokenError("Token format is invalid") from exc
    if not hmac.compare_digest(signature, _sign(encoded_payload, settings.auth_secret_key)):
        raise AuthTokenError("Token signature is invalid")
    try:
        payload = json.loads(_base64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthTokenError("Token payload is invalid") from exc
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        raise AuthTokenError("Token has expired")
    return payload


def ensure_user_can_login(user: User | None) -> User:
    if user is None:
        raise AuthTokenError("User not found")
    if user.status != UserStatus.ACTIVE:
        raise AuthTokenError("User is disabled")
    return user


def _sign(encoded_payload: str, secret_key: str) -> str:
    digest = hmac.new(secret_key.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return _base64url_encode(digest)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))