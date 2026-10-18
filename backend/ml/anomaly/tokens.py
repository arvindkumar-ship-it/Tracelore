from typing import Any

START, END, UNKNOWN = "<START>", "<END>", "<UNK>"


def tokenize(event: dict[str, Any]) -> str:
    attributes, kind = event["attributes"], event["type"]
    if kind == "http.request":
        return f"http.request:{event['service']}:{attributes['route']}"
    if kind == "http.client":
        return f"http.client:{event['service']}->{attributes['downstream_service']}"
    if kind == "db.query":
        return f"db.query:{attributes['operation']}:{attributes['db_table'] or '*'}"
    if kind == "cache.get":
        return "cache.get:hit" if attributes["hit"] else "cache.get:miss"
    if kind in ("cache.set", "cache.delete"):
        return str(kind)
    if kind.startswith("queue."):
        return f"{kind}:{attributes['queue']}"
    if kind == "error":
        return f"error:{attributes['exception_type']}"
    raise ValueError(f"unknown event type {kind}")
