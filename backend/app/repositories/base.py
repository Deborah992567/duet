"""Generic repository primitives.

All persistence flows through repositories so the database implementation can
be swapped (e.g. MariaDB -> Postgres) without touching service logic.
"""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.orm import Session

from app.db.session import Base

ModelT = TypeVar("ModelT", bound=Base)


def new_uuid() -> str:
    return uuid.uuid4().hex


def encode_cursor(value: tuple[Any, ...] | list[Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(list(value)).encode()).decode()


def decode_cursor(cursor: str | None) -> list[Any] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode() + b"====")
        return json.loads(raw)
    except Exception:
        return None


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, _id: str) -> ModelT | None:
        return self.db.get(self.model, _id)

    def get_or_raise(self, _id: str) -> ModelT:
        obj = self.get(_id)
        if obj is None:
            raise self.not_found_exc("The requested resource could not be found.")
        return obj

    @staticmethod
    def not_found_exc(message: str = "The requested resource could not be found."):
        from app.core.errors import NotFoundError

        return NotFoundError(message)

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        return obj

    def add_all(self, objs: list[ModelT]) -> None:
        self.db.add_all(objs)

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)

    def delete_by_id(self, _id: str) -> bool:
        stmt = delete(self.model).where(self.model.id == _id)
        result = self.db.execute(stmt)
        return result.rowcount > 0

    def update_fields(self, _id: str, **fields: Any) -> ModelT | None:
        if not fields:
            return self.get(_id)
        values = {k: v for k, v in fields.items() if v is not None}
        if not values:
            return self.get(_id)
        stmt = update(self.model).where(self.model.id == _id).values(**values)
        self.db.execute(stmt)
        self.db.flush()
        return self.get(_id)

    def count(self, *where: Any) -> int:
        stmt = select(func.count()).select_from(self.model).where(*where)
        return int(self.db.scalar(stmt) or 0)

    def _paginate(self, stmt: Select, limit: int, cursor: list[Any] | None) -> tuple[list[Any], str | None]:
        raise NotImplementedError

    def exists(self, *where: Any) -> bool:
        stmt = select(func.count()).select_from(self.model).where(*where)
        return int(self.db.scalar(stmt) or 0) > 0