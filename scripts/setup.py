"""Create local credentials once; never replace an existing environment file."""

import secrets
from pathlib import Path


def configure(root: Path) -> bool:
    destination = root / ".env"
    if destination.exists():
        return False
    credentials = {
        name: secrets.token_urlsafe(36)
        for name in (
            "POSTGRES_PASSWORD",
            "TRACELORE_APP_PASSWORD",
            "TRACELORE_OWNER_PASSWORD",
            "TRACELORE_SECRET",
            "S3_SECRET_KEY",
            "DEMO_TOKEN",
            "DEMO_INGEST_KEY",
        )
    }
    credentials["S3_ACCESS_KEY"] = "tracelore-" + secrets.token_hex(8)
    credentials["DATABASE_URL"] = (
        f"postgresql://tracelore_app:{credentials['TRACELORE_APP_PASSWORD']}@localhost:5432/tracelore"
    )
    credentials["OWNER_DATABASE_URL"] = (
        f"postgresql://tracelore_owner:{credentials['TRACELORE_OWNER_PASSWORD']}@localhost:5432/tracelore"
    )
    content = (
        "\n".join(
            f"{key}={credentials.get(key, value)}" if "=" in line else line
            for line in (root / ".env.example").read_text().splitlines()
            for key, _, value in [line.partition("=")]
        )
        + "\n"
    )
    with destination.open("x") as handle:
        handle.write(content)
    destination.chmod(0o600)
    return True


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    created = configure(Path(__file__).resolve().parents[1])
    logging.getLogger(__name__).info("environment_ready created=%s", created)
