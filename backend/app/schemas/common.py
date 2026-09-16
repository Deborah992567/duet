"""Common Pydantic schemas: pagination, cursor helpers, IDs."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.config import settings

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class BaseQuery(BaseModel):
    limit: int = Field(default=settings.default_page_size, ge=1, le=settings.max_page_size)
    cursor: str | None = None