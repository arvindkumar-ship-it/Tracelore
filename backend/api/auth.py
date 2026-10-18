import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, SecretStr
from tracelore.canonical import canonical_json

from backend.common.errors import ApiError, Code
from backend.common.settings import Settings

TOKEN_HOURS = 8
bearer = HTTPBearer(auto_error=False)


class LoginInput(BaseModel):
    secret: SecretStr


class TokenView(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth wire constant, not a credential.
    expires_at: datetime


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def issue_token(settings: Settings, at: datetime) -> TokenView:
    expires = at + timedelta(hours=TOKEN_HOURS)
    payload = _encode(
        canonical_json(
            {"exp": int(expires.timestamp()), "scope": "dashboard", "nonce": secrets.token_hex(16)}
        )
    )
    signature = hmac.new(
        settings.tracelore_secret.get_secret_value().encode(), payload.encode(), hashlib.sha256
    ).digest()
    return TokenView(access_token=payload + "." + _encode(signature), expires_at=expires)


def verify_token(token: str, settings: Settings, at: datetime) -> None:
    try:
        if len(token) > 2048:
            raise ValueError("oversized token")
        payload, signature = token.split(".")
        expected = hmac.new(
            settings.tracelore_secret.get_secret_value().encode(), payload.encode(), hashlib.sha256
        ).digest()
        actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, actual):
            raise ValueError("invalid signature")
        values = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if values.get("scope") != "dashboard" or values["exp"] <= at.timestamp():
            raise ValueError("token expired or scope invalid")
    except (ValueError, KeyError, TypeError) as error:
        raise ApiError(Code.UNAUTHORIZED, "Invalid or expired dashboard token", 401) from error


async def require_dashboard(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> None:
    if credentials is None:
        raise ApiError(Code.UNAUTHORIZED, "Dashboard bearer token required", 401)
    verify_token(credentials.credentials, request.app.state.settings, datetime.now(UTC))
