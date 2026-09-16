"""Media upload schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.constants import MediaKind


class BeginUploadPayload(BaseModel):
    kind: MediaKind
    file_name: str = Field(max_length=255)
    size_bytes: int = Field(gt=0, le=100 * 1024 * 1024)
    mime_type: str = Field(max_length=128)
    checksum_sha256: str | None = Field(default=None, max_length=64)


class BeginUploadResponse(BaseModel):
    upload_id: str
    upload_url: str | None = None  # presigned S3 URL when using S3; None for direct POST
    upload_fields: dict = Field(default_factory=dict)  # S3 multipart form fields
    expires_at: int = 0
    headers: dict[str, str] = Field(default_factory=dict)
    method: str = "PUT"


class CompleteUploadPayload(BaseModel):
    upload_id: str
    object_key: str | None = None


class AttachmentOut(BaseModel):
    id: str
    kind: str
    url: str
    thumb_url: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    file_name: str | None = None
    waveform: list[int] | None = None
    model_config = {"from_attributes": True}


class AvatarUploadOut(BaseModel):
    avatar_url: str
    avatar_thumb_url: str | None = None