import re

from ..canonical import hash_payload

STRING_LITERAL = re.compile(r"'(?:''|[^'])*'|\$[A-Za-z_]*\$.*?\$[A-Za-z_]*\$", re.DOTALL)
NUMERIC_LITERAL = re.compile(r"\b\d+(?:\.\d+)?\b|\$\d+|:[A-Za-z_]\w*")
SQL_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
TABLE = re.compile(r"\b(?:from|into|update)\s+([a-z_][\w.]*)")


def normalize_sql(sql: str) -> str:
    normalized = STRING_LITERAL.sub("?", sql)
    normalized = SQL_COMMENTS.sub(" ", normalized)
    normalized = NUMERIC_LITERAL.sub("?", normalized)
    return " ".join(normalized.lower().split())


def parse_table_and_operation(normalized: str) -> tuple[str, str | None]:
    operation = normalized.split(" ", 1)[0]
    if operation not in ("select", "insert", "update", "delete"):
        return "other", None
    match = TABLE.search(normalized)
    return operation, match.group(1) if match else None


def query_attributes(query: str, rows: int | None = None) -> dict[str, str | int | None]:
    normalized = normalize_sql(query)
    operation, table = parse_table_and_operation(normalized)
    return {
        "operation": operation,
        "db_table": table,
        "query_hash": hash_payload(normalized),
        "rows": rows if rows is not None and rows >= 0 else None,
    }
