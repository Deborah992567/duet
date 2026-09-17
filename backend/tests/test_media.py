"""Media upload seam: begin → PUT content → complete → attach to a voice message."""

from __future__ import annotations

import hashlib

from app.core.config import settings
from tests.conftest import auth_headers

PAYLOAD = b"\x00\x01\x02\x03 something recorded-ish"


def _checksum() -> str:
    return hashlib.sha256(PAYLOAD).hexdigest()


def _uploads(client, auth):
    return client.post(
        "/v1/media/uploads",
        json={
            "kind": "voice",
            "file_name": "talk.m4a",
            "size_bytes": len(PAYLOAD),
            "mime_type": "audio/mp4",
            "checksum_sha256": _checksum(),
        },
        headers=auth,
    )


def test_upload_lifecycle_and_voice_message(client, two_friends, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_local_path", str(tmp_path))
    alice, bob = two_friends
    headers = auth_headers(alice)

    begin = _uploads(client, headers)
    assert begin.status_code == 200, begin.text
    upload_id = begin.json()["upload_id"]
    assert begin.json()["method"] == "PUT"

    stored = client.put(
        f"/v1/media/{upload_id}/content",
        content=PAYLOAD,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    assert stored.status_code == 201, stored.text

    complete = client.post(
        f"/v1/media/uploads/{upload_id}/complete",
        headers=headers,
    )
    assert complete.status_code == 200, complete.text
    assert "content" in complete.json()["url"]

    conv = client.post(
        "/v1/conversations",
        json={"user_id": bob["user"]["id"]},
        headers=headers,
    )
    assert conv.status_code == 201, conv.text
    conv_id = conv.json()["id"]

    sent = client.post(
        f"/v1/conversations/{conv_id}/messages",
        json={
            "kind": "voice",
            "client_id": "voice-test-1",
            "attachments": [
                {
                    "upload_id": upload_id,
                    "kind": "voice",
                    "file_name": "talk.m4a",
                    "size_bytes": len(PAYLOAD),
                    "duration_ms": 2100,
                }
            ],
        },
        headers=headers,
    )
    assert sent.status_code == 201 or sent.status_code == 200, sent.text
    message = sent.json()["message"]
    assert message["kind"] == "voice"
    assert message["attachments"][0]["duration_ms"] == 2100
    assert message["attachments"][0]["url"].startswith("/v1/media/")


def test_upload_requires_matching_checksum(client):
    from tests.conftest import register_user

    alice = register_user(client, "alice_media@example.com", "alice_media")
    headers = auth_headers(alice)
    begin = _uploads(client, headers)
    upload_id = begin.json()["upload_id"]
    stored = client.put(
        f"/v1/media/{upload_id}/content",
        content=b"corrupted-bytes-that-will-not-match",
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    assert stored.status_code == 422, stored.text


def test_upload_rejects_unsupported_type(client):
    from tests.conftest import register_user

    alice = register_user(client, "alice_type@example.com", "alice_type")
    headers = auth_headers(alice)
    r = client.post(
        "/v1/media/uploads",
        json={"kind": "voice", "file_name": "weird.exe", "size_bytes": 4, "mime_type": "application/x-msdownload"},
        headers=headers,
    )
    assert r.status_code == 422, r.text