"""Pytest fixtures: isolated SQLite DB + fakeredis + TestClient."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

import fakeredis.aioredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: F401, E402  (register all tables)
from app.core.redis_client import set_current_redis  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.db.session import Base  # noqa: E402

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _sqlite_greatest(dbapi_conn, _record):
    dbapi_conn.create_function("greatest", -1, lambda *a: max(a))

db_session.engine = engine
db_session.SessionLocal = TestingSession

# Import the app *after* swapping the DB engine so lifespan/create_all use SQLite.
from app.main import app  # noqa: E402

app.state.session_factory = TestingSession

Base.metadata.create_all(bind=engine)

_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
set_current_redis(_redis)


def override_get_db():
    db = TestingSession()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app.dependency_overrides[db_session.get_db] = override_get_db


@pytest.fixture()
def client():
    import asyncio

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    asyncio.run(_redis.flushall())
    with TestClient(app) as c:
        yield c


def register_user(c: TestClient, email: str, username: str, password: str = "supersecret1") -> dict:
    r = c.post(
        "/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "display_name": username.title(),
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def login(c: TestClient, identifier: str, password: str = "supersecret1") -> dict:
    r = c.post("/v1/auth/login", json={"identifier": identifier, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def two_users(client):
    a = register_user(client, "alice@example.com", "alice")
    b = register_user(client, "bob@example.com", "bob")
    return a, b


@pytest.fixture()
def two_friends(client):
    """Alice and Bob registered AND friends. Auths are register responses with tokens."""
    from tests.test_friends import make_friends

    alice = register_user(client, "alice_f@example.com", "alice_f")
    bob = register_user(client, "bob_f@example.com", "bob_f")
    make_friends(client, alice, bob)
    return alice, bob


def auth_headers(auth: dict) -> dict:
    access = auth.get("access_token") or auth["tokens"]["access_token"]
    return {"Authorization": f"Bearer {access}"}