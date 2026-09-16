"""Media routes: begin upload, PUT content, complete, stream."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.schemas.media import BeginUploadPayload, BeginUploadResponse
from app.services.media_service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


def svc(db: Session) -> MediaService:
    return MediaService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.post("/uploads")
async def begin_upload(payload: BeginUploadPayload, db: SessionDep, user: CurrentUser) -> BeginUploadResponse:
    return await svc(db).begin(
        kind=payload.kind,
        file_name=payload.file_name,
        size_bytes=payload.size_bytes,
        mime_type=payload.mime_type,
        checksum_sha256=payload.checksum_sha256,
    )


@router.put("/{upload_id}/content", status_code=201)
async def save_content(upload_id: str, request: Request, db: SessionDep, user: CurrentUser):
    """Receives the raw object bytes (local backend)."""
    data = await request.body()
    record = await svc(db).save(upload_id, data)
    return {"status": "stored", "size_bytes": len(data)}


@router.post("/uploads/{upload_id}/complete")
async def complete(upload_id: str, db: SessionDep, user: CurrentUser):
    url = await svc(db).complete(upload_id)
    return {"url": url}


@router.get("/{upload_id}/content")
async def stream(upload_id: str, db: SessionDep, user: CurrentUser):
    mime, path = await svc(db).stream(upload_id)
    return FileResponse(path, media_type=mime)