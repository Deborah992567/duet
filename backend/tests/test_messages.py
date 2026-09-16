"""Message send/edit/react/read-receipt/search tests."""

from tests.conftest import auth_headers, login


def _conv(client, tokens, peer_auth):
    """Create (or reuse) the direct conversation between `tokens` and `peer_auth`."""
    items = client.get("/v1/conversations", headers=auth_headers(tokens)).json()["items"]
    if items:
        return items[0]["id"]
    return client.post(
        "/v1/conversations", json={"user_id": peer_auth["user"]["id"]}, headers=auth_headers(tokens)
    ).json()["id"]


def test_send_and_list(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    r = client.post(
        f"/v1/conversations/{cid}/messages",
        json={"body": "hello bob"},
        headers=auth_headers(alice),
    )
    assert r.status_code == 200
    msg = r.json()["message"]
    assert msg["body"] == "hello bob"
    assert msg["conversation_id"] == cid
    list_resp = client.get(f"/v1/conversations/{cid}/messages", headers=auth_headers(alice)).json()
    assert any(m["body"] == "hello bob" for m in list_resp["items"])


def test_send_requires_membership(client, two_users):
    from tests.conftest import register_user

    alice, bob = two_users
    at = login(client, "alice@example.com")
    register_user(client, "stranger@example.com", "stranger")
    st = login(client, "stranger@example.com")
    conv = client.post("/v1/conversations", json={"user_id": bob["user"]["id"]}, headers=auth_headers(at)).json()
    r = client.post(f"/v1/conversations/{conv['id']}/messages", json={"body": "intrude"}, headers=auth_headers(st))
    assert r.status_code in (403, 404)


def test_deduct_duplicate_client_id(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    payload = {"body": "first", "client_id": "dup-1"}
    r1 = client.post(f"/v1/conversations/{cid}/messages", json=payload, headers=auth_headers(alice))
    r2 = client.post(f"/v1/conversations/{cid}/messages", json=payload, headers=auth_headers(alice))
    assert r1.json()["message"]["id"] == r2.json()["message"]["id"]
    msgs = client.get(f"/v1/conversations/{cid}/messages", headers=auth_headers(alice)).json()
    assert sum(1 for m in msgs["items"] if m.get("client_id") == "dup-1") == 1


def test_edit_message(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    mid = client.post(f"/v1/conversations/{cid}/messages", json={"body": "orig"}, headers=auth_headers(alice)).json()["message"]["id"]
    r = client.patch(f"/v1/conversations/{cid}/messages/{mid}", json={"body": "edited"}, headers=auth_headers(alice))
    assert r.json()["body"] == "edited"


def test_delete_and_verify(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    mid = client.post(f"/v1/conversations/{cid}/messages", json={"body": "doomed"}, headers=auth_headers(alice)).json()["message"]["id"]
    r = client.request("DELETE", f"/v1/conversations/{cid}/messages/{mid}", json={"delete_for": "everyone"}, headers=auth_headers(alice))
    assert r.status_code == 204
    msgs = client.get(f"/v1/conversations/{cid}/messages", headers=auth_headers(alice)).json()
    row = next(m for m in msgs["items"] if m["id"] == mid)
    assert row["body"] is None


def test_react_and_unreact(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    mid = client.post(f"/v1/conversations/{cid}/messages", json={"body": "react me"}, headers=auth_headers(alice)).json()["message"]["id"]
    client.post(f"/v1/conversations/{cid}/messages/{mid}/react", json={"emoji": "🔥"}, headers=auth_headers(bob))
    msgs = client.get(f"/v1/conversations/{cid}/messages", headers=auth_headers(alice)).json()["items"]
    detail = next(m for m in msgs if m["id"] == mid)
    assert any(rx["emoji"] == "🔥" for rx in detail["reactions"])
    client.request("DELETE", f"/v1/conversations/{cid}/messages/{mid}/react/%F0%9F%94%A5", json={}, headers=auth_headers(bob))
    msgs2 = client.get(f"/v1/conversations/{cid}/messages", headers=auth_headers(alice)).json()["items"]
    detail2 = next(m for m in msgs2 if m["id"] == mid)
    assert not any(rx["emoji"] == "🔥" for rx in detail2["reactions"])


def test_read_receipt_flow(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    mid = client.post(f"/v1/conversations/{cid}/messages", json={"body": "petit"}, headers=auth_headers(alice)).json()["message"]["id"]
    client.post(f"/v1/conversations/{cid}/receipts/read", json={"up_to_message_id": mid}, headers=auth_headers(bob))
    conv = client.get(f"/v1/conversations/{cid}", headers=auth_headers(bob)).json()
    assert conv["unread_count"] == 0


def test_search_messages(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    client.post(f"/v1/conversations/{cid}/messages", json={"body": "trouver ceci"}, headers=auth_headers(alice))
    r = client.post("/v1/conversations/messages/search", json={"query": "trouver ceci"}, headers=auth_headers(alice))
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


def test_typing_signal(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    r = client.post(f"/v1/conversations/{cid}/typing", headers=auth_headers(alice))
    assert r.status_code == 204