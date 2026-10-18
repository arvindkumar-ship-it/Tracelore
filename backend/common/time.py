from datetime import UTC, datetime

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def parse_timestamp(value: str | datetime) -> datetime:
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed.astimezone(UTC)


def microseconds(value: str | datetime) -> int:
    delta = parse_timestamp(value) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
