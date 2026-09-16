"""Streak engine + read-API tests. Engine is the source of truth for matches."""

import asyncio
from datetime import date, datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.services.streak_engine import StreakEngine
from tests.conftest import auth_headers


def _conversation_id(client, tokens, peer):
    return client.post(
        "/v1/conversations", json={"user_id": peer["user"]["id"]}, headers=auth_headers(tokens)
    ).json()["id"]


def _at(d: date, hour: int = 12) -> datetime:
    return datetime.combine(d, datetime.min.time().replace(hour=hour), tzinfo=timezone.utc)


def _both_active(engine, alice_id, bob_id, cid, day):
    asyncio.run(engine.record_activity(actor_id=alice_id, peer_user_id=bob_id, conversation_id=cid, sent_at=_at(day)))
    asyncio.run(engine.record_activity(actor_id=bob_id, peer_user_id=alice_id, conversation_id=cid, sent_at=_at(day)))


def test_both_active_same_day(client, two_friends):
    alice, bob = two_friends
    cid = _conversation_id(client, alice, bob)
    _both_active(StreakEngine(SessionLocal()), alice["user"]["id"], bob["user"]["id"], cid, date.today())
    streak = client.get(f"/v1/streaks/{cid}/with/{bob['user']['id']}", headers=auth_headers(alice)).json()
    assert streak["current_streak"] == 1
    assert streak["alive"] is True


def test_single_sided_does_not_count(client, two_friends):
    alice, bob = two_friends
    cid = _conversation_id(client, alice, bob)
    engine = StreakEngine(SessionLocal())
    asyncio.run(engine.record_activity(actor_id=alice["user"]["id"], peer_user_id=bob["user"]["id"], conversation_id=cid, sent_at=_at(date.today())))
    streak = client.get(f"/v1/streaks/{cid}/with/{bob['user']['id']}", headers=auth_headers(alice)).json()
    assert streak["current_streak"] == 0


def test_two_day_streak_and_break(client, two_friends):
    alice, bob = two_friends
    cid = _conversation_id(client, alice, bob)
    d1 = date.today()
    _both_active(StreakEngine(SessionLocal()), alice["user"]["id"], bob["user"]["id"], cid, d1)
    _both_active(StreakEngine(SessionLocal()), alice["user"]["id"], bob["user"]["id"], cid, d1 + timedelta(days=1))
    streak = client.get(f"/v1/streaks/{cid}/with/{bob['user']['id']}", headers=auth_headers(alice)).json()
    assert streak["current_streak"] >= 2
    db_expired = SessionLocal()
    asyncio.run(StreakEngine(db_expired, today=d1 + timedelta(days=3)).expire_stale(today=d1 + timedelta(days=3)))
    db_expired.close()
    streak2 = client.get(f"/v1/streaks/{cid}/with/{bob['user']['id']}", headers=auth_headers(alice)).json()
    assert streak2["alive"] is False


def test_settings_toggle(client, two_friends):
    alice, bob = two_friends
    r = client.patch("/v1/streaks/me/settings", json={"visible": False, "reminders_enabled": True}, headers=auth_headers(alice))
    assert r.status_code == 200
    assert r.json()["visible"] is False
    assert r.json()["reminders_enabled"] is True