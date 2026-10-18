import base64
import json
from datetime import datetime

from tracelore.canonical import canonical_json

from .errors import ApiError, Code


def encode_cursor(at: datetime, identifier: str) -> str:
    return base64.urlsafe_b64encode(canonical_json([at.isoformat(), identifier])).decode()


def decode_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
    if cursor is None:
        return None, None
    try:
        if len(cursor) > 512:
            raise ValueError("oversized cursor")
        fields = json.loads(base64.urlsafe_b64decode(cursor))
        if not isinstance(fields, list) or len(fields) != 2:
            raise ValueError("invalid cursor shape")
        at, identifier = fields
        parsed = datetime.fromisoformat(at)
        if parsed.tzinfo is None or not isinstance(identifier, str):
            raise ValueError("invalid cursor fields")
        return parsed, identifier
    except (ValueError, TypeError) as error:
        raise ApiError(Code.BAD_REQUEST, "Invalid pagination cursor") from error
