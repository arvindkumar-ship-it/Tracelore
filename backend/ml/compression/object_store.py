import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from tracelore.canonical import canonical_json

from backend.common.metrics import DIGEST_MISMATCH
from backend.common.settings import Settings

from .decoder import validate_file
from .encoder import EncodedFile


class ObjectStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        )

    async def ensure_bucket(self) -> None:
        await asyncio.to_thread(self._ensure_bucket)

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.settings.s3_bucket)
        except ClientError as error:
            if error.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise
            self.client.create_bucket(Bucket=self.settings.s3_bucket)

    async def upload(self, encoded: EncodedFile, object_key: str) -> None:
        for path, key in [
            (encoded.path, object_key),
            (encoded.index_path, object_key.replace(".parquet", ".index.parquet")),
            (encoded.manifest_path, object_key.replace(".parquet", ".manifest.json")),
        ]:
            await asyncio.to_thread(
                self.client.upload_file, str(path), self.settings.s3_bucket, key
            )
        # Verify remote bytes, not just the local file that was uploaded.
        destination = self.settings.archive_dir / "remote-verify" / encoded.path.name
        await self.download(object_key, destination, force=True, expected_manifest=encoded.manifest)
        await asyncio.to_thread(validate_file, destination)

    async def download(
        self,
        object_key: str,
        path: Path,
        force: bool = False,
        expected_manifest: dict[str, Any] | None = None,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            await asyncio.to_thread(_validate_expected, path, expected_manifest)
            return path
        for suffix in (".index.parquet", ".manifest.json", ".parquet"):
            target = path.with_suffix(suffix)
            key = object_key.removesuffix(".parquet") + suffix
            temporary = target.with_suffix(target.suffix + f".{uuid4().hex}.partial")
            await asyncio.to_thread(
                self.client.download_file, self.settings.s3_bucket, key, str(temporary)
            )
            temporary.replace(target)
        await asyncio.to_thread(_validate_expected, path, expected_manifest)
        return path


def _validate_expected(path: Path, expected: dict[str, Any] | None) -> None:
    manifest = validate_file(path)
    if expected is not None and canonical_json(manifest) != canonical_json(expected):
        DIGEST_MISMATCH.inc()
        raise ValueError("Archive manifest differs from its protected ledger anchor")
