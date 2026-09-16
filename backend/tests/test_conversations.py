"""Conversation (direct + group) tests."""

from tests.conftest import auth_headers, login, register_user


def _conv(client, tokens, peer_auth):
    items = client.get("/v1/conversations", headers=auth_headers(tokens)).json()["items"]
    if items:
        return items[0]["id"]
    return client.post(
        "/v1/conversations", json={"user_id": peer_auth["user"]["id"]}, headers=auth_headers(tokens)
    ).json()["id"]


def test_create_direct_conversation(client, two_friends):
    alice, bob = two_friends
    r = client.post(
        "/v1/conversations",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["type"] == "direct"


def test_create_group(client, two_users):
    alice, bob = two_users
    at = a_tokens = login(client, "alice@example.com")
    bt = login(client, "bob@example.com")
    r = client.post(
        "/v1/conversations/groups",
        json={"name": "Secret Club", "member_ids": [bob["user"]["id"]]},
        headers=auth_headers(at),
    )
    assert r.status_code == 201
    assert r.json()["type"] == "group"
    member_ids = client.get(f"/v1/conversations/{r.json()['id']}", headers=auth_headers(bt)).json()["members"]
    assert {m["user"]["id"] for m in member_ids} == {alice["user"]["id"], bob["user"]["id"]}


def test_list_only_member_conversations(client, two_users):
    alice, bob = two_users
    at = login(client, "alice@example.com")
    other = register_user(client, "carol@example.com", "carol1")
    ot = login(client, "carol@example.com")
    # alice + carol in a convo; bob not
    conv = client.post(
        "/v1/conversations", json={"user_id": other["user"]["id"]}, headers=auth_headers(at)
    ).json()
    bt = login(client, "bob@example.com")
    r = client.get("/v1/conversations", headers=auth_headers(bt))
    assert r.status_code == 200
    assert all(c["id"] != conv["id"] for c in r.json()["items"])


def test_mark_read_clears_unread(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    client.post(
        f"/v1/conversations/{cid}/messages",
        json={"body": "hello bob"},
        headers=auth_headers(bob),
    )
    before = client.get(f"/v1/conversations/{cid}", headers=auth_headers(alice)).json()
    assert before["unread_count"] >= 1
    msgs = client.get(f"/v1/conversations/{cid}/messages", headers=auth_headers(alice)).json()
    last_id = msgs["items"][0]["id"]
    client.post(f"/v1/conversations/{cid}/read", json={"up_to_message_id": last_id}, headers=auth_headers(alice))
    after = client.get(f"/v1/conversations/{cid}", headers=auth_headers(alice)).json()
    assert after["unread_count"] == 0


def test_mute_and_pin(client, two_friends):
    alice, bob = two_friends
    cid = _conv(client, alice, bob)
    client.post(f"/v1/conversations/{cid}/mute", json={"muted": True}, headers=auth_headers(alice))
    client.post(f"/v1/conversations/{cid}/pin", json={"pinned": True}, headers=auth_headers(alice))
    detail = client.get(f"/v1/conversations/{cid}", headers=auth_headers(alice)).json()
    assert detail["is_muted"] is True
    assert detail["is_pinned"] is True


def test_group_admin_lifecycle(client, two_users):
    alice, bob = two_users
    at = login(client, "alice@example.com")
    carol = register_user(client, "carol_g@example.com", "carolg")
    ct = login(client, "carol_g@example.com")
    group = client.post(
        "/v1/conversations/groups",
        json={"name": "Team", "member_ids": [bob["user"]["id"], carol["user"]["id"]]},
        headers=auth_headers(at),
    ).json()
    gid = group["id"]
    # promote bob to admin
    bt = login(client, "bob@example.com")
    client.post(f"/v1/conversations/{gid}/members/{bob['user']['id']}/promote", headers=auth_headers(at))
    # admin adds a member
    client.post(f"/v1/conversations/{gid}/members", json={"member_ids": []}, headers=auth_headers(bt))
    # leave works
    r = client.post(f"/v1/conversations/{gid}/leave", headers=auth_headers(ct))
    assert r.status_code == 204


def test_remove_member_requires_admin(client, two_users):
    alice, bob = two_users
    at = login(client, "alice@example.com")
    group = client.post(
        "/v1/conversations/groups",
        json={"name": "Squad", "member_ids": [bob["user"]["id"]]},
        headers=auth_headers(at),
    ).json()
    gid = group["id"]
    bt = login(client, "bob@example.com")
    r = client.request(
        "DELETE",
        f"/v1/conversations/{gid}/members/{alice['user']['id']}",
        headers=auth_headers(bt),
    )
    assert r.status_code == 403