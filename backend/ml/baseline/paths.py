from pathlib import Path

from tracelore.canonical import canonical_json, hash_payload


def endpoint_model_dir(root: Path, service: str, route: str) -> Path:
    return root / "endpoints" / hash_payload(canonical_json([service, route]))[:24]
