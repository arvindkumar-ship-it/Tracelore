import logging
import re

SECRET_PATTERN = re.compile(
    r"(?i)((?:authorization|x-api-key|api_key|secret)[\"']?\s*[:=]\s*[\"']?)"
    r"(?:bearer\s+)?[^\s,}\"']+"
)
DATABASE_PASSWORD = re.compile(r"(postgres(?:ql)?://[^:@/]+:)[^@/\s]+@")


def redact(value: str) -> str:
    return DATABASE_PASSWORD.sub(r"\1[REDACTED]@", SECRET_PATTERN.sub(r"\1[REDACTED]", value))


class RedactSecrets(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg, record.args = redact(record.getMessage()), ()
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactSecrets())
    handler.setFormatter(
        RedactingFormatter("%(asctime)s level=%(levelname)s logger=%(name)s %(message)s")
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
