"""Media upload/object-storage service.

Backend abstraction over local disk or S3-compatible object storage. Uploads are
referenced by an `upload_id` that doubles as the object key, so message
attachment URLs stay stable. Local storage is the portable dev default; S3 is
selected via config without touching business logic.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import MediaKind
from app.core.errors import NotFoundError, ServiceUnavailableError, ValidationAppError
from app.schemas.media import BeginUploadResponse
from app.services.base import Service

UPLOAD_TTL = 3600 * 24  # 24h


class MediaService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self._local_root = Path(settings.media_local_path)

    # ------------------------------------------------------------------ #
    # Upload lifecycle
    # ------------------------------------------------------------------ #

    async def begin(self, *, kind: MediaKind, file_name: str, size_bytes: int, mime_type: str,
                    checksum_sha256: Optional[str] = None) -> BeginUploadResponse:
        if size_bytes > settings.media_max_upload_bytes:
            raise ValidationAppError("This file is too large to upload.", code="file_too_large")
        if not self._allowed_kind(kind, mime_type):
            raise ValidationAppError("This file type is not supported.", code="unsupported_type")

        upload_id = _new_upload_id()
        record = {
            "upload_id": upload_id,
            "kind": kind.value if hasattr(kind, "value") else kind,
            "file_name": file_name,
            "size_bytes": size_bytes,
            "mime_type": mime_type,
            "checksum_sha256": checksum_sha256,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.redis is None:
            raise ServiceUnavailableError("Media upload service is not configured.", code="media_unavailable")
        await self.redis.set(f"media:upload:{upload_id}", json.dumps(record), ex=UPLOAD_TTL)

        if settings.media_storage_backend == "s3":
            upload_url, fields, headers, method = await self._s3_presign(upload_id, mime_type)
            return BeginUploadResponse(
                upload_id=upload_id, upload_url=upload_url, upload_fields=fields,
                headers=headers, method=method, expires_at=int(time() + 3600)
            )
        return BeginUploadResponse(
            upload_id=upload_id,
            upload_url=f"{settings.api_prefix}/media/{upload_id}/content",
            method="PUT",
            expires_at=int(time() + 3600),
            headers={"Content-Type": mime_type},
        )

    async def save(self, upload_id: str, data: bytes) -> dict:
        record = await self._get_record(upload_id)
        if record is None:
            raise NotFoundError("This upload no longer exists or has expired.", code="upload_expired")
        if settings.media_storage_backend == "s3":
            raise ServiceUnavailableError("Direct upload is not supported for this deployment.", code="s3_direct_upload")
        actual = len(data)
        expected = record["size_bytes"]
        if actual != expected:
            raise ValidationAppError("Uploaded file size does not match the declared size.", code="size_mismatch")
        if record.get("checksum_sha256"):
            digest = hashlib.sha256(data).hexdigest()
            if digest != record["checksum_sha256"]:
                raise ValidationAppError("Upload checksum mismatch.", code="checksum_mismatch")
        path = self._local_root / record["kind"] / upload_id
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        await self.redis.set(
            f"media:upload:{upload_id}", json.dumps({**record, "stored": True}), ex=UPLOAD_TTL
        )
        record["stored"] = True
        return record

    async def complete(self, upload_id: str) -> str:
        record = await self._get_record(upload_id)
        if record is None:
            raise NotFoundError("This upload no longer exists or has expired.", code="upload_expired")
        if not record.get("stored") and settings.media_storage_backend != "s3":
            raise ValidationAppError("Upload data is not present yet.", code="upload_incomplete")
        return f"{settings.api_prefix}/media/{upload_id}/content"

    async def stream(self, upload_id: str):
        """Returns (mime_type, file_path) for a stored upload."""
        record = await self._get_record(upload_id)
        if record is None:
            raise NotFoundError("Content not found.", code="content_not_found")
        path = self._local_root / record["kind"] / upload_id
        if not path.exists():
            raise NotFoundError("Content not found.", code="content_missing")
        return record["mime_type"], path

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    async def _get_record(self, upload_id: str) -> Optional[dict]:
        if self.redis is None:
            return None
        raw = await self.redis.get(f"media:upload:{upload_id}")
        return json.loads(raw) if raw else None

    async def _s3_presign(self, upload_id: str, mime_type: str):
        # Preserved seam for production S3 deployments.
        raise ServiceUnavailableError(
            "Object storage is not configured in this environment.", code="s3_not_configured"
        )

    @staticmethod
    def _allowed_kind(kind, mime_type: str) -> bool:
        kind_v = kind.value if hasattr(kind, "value") else kind
        if kind_v in (MediaKind.AVATAR,):
            return mime_type.startswith("image/")
        if kind_v == MediaKind.IMAGE:
            return mime_type.startswith("image/")
        if kind_v == MediaKind.VIDEO:
            return mime_type.startswith("video/")
        if kind_v == MediaKind.VOICE:
            return mime_type in ("audio/mp4", "audio/mpeg", "audio/aac", "audio/m4a", "audio/wav", "audio/ogg")
        if kind_v in (MediaKind.FILE, MediaKind.STICKER, MediaKind.GIF):
            return True
        return False


def _new_upload_id() -> str:
    return hashlib.sha256(os.urandom(16)).hexdigest()[:32]


def time() -> int:
    from time import time as _t

    return int(_t())