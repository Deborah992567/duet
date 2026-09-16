"""Friendship / friend-request tests."""

from tests.conftest import auth_headers, login, register_user


def make_friends(client, a_tokens, b):
    """Alice -> Bob request, Bob accepts."""
    r = client.post(
        "/v1/friends/requests",
        json={"user_id": b["user"]["id"], "message": "hi"},
        headers=auth_headers(a_tokens),
    )
    request_id = r.json()["request_id"]
    b_tokens = login(client, "bob@example.com")
    r2 = client.post(
        f"/v1/friends/requests/{request_id}/respond",
        json={"accept": True},
        headers=auth_headers(b_tokens),
    )
    assert r2.status_code == 204


def test_send_and_accept(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    bob_tokens = login(client, "bob@example.com")

    r = client.post(
        "/v1/friends/requests",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice_tokens),
    )
    assert r.status_code == 200
    request_id = r.json()["request_id"]

    incoming = client.get("/v1/friends/requests/incoming", headers=auth_headers(bob_tokens)).json()
    assert len(incoming) == 1

    r2 = client.post(
        f"/v1/friends/requests/{request_id}/respond",
        json={"accept": True},
        headers=auth_headers(bob_tokens),
    )
    assert r2.status_code == 204

    friends = client.get("/v1/friends", headers=auth_headers(alice_tokens)).json()
    assert len(friends["items"]) == 1


def test_decline(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    bob_tokens = login(client, "bob@example.com")
    r = client.post("/v1/friends/requests", json={"user_id": bob["user"]["id"]}, headers=auth_headers(alice_tokens))
    request_id = r.json()["request_id"]
    r2 = client.post(f"/v1/friends/requests/{request_id}/respond", json={"accept": False}, headers=auth_headers(bob_tokens))
    assert r2.status_code == 204
    friends = client.get("/v1/friends", headers=auth_headers(alice_tokens)).json()
    assert friends["items"] == []


def test_duplicate_request_rejected(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    client.post("/v1/friends/requests", json={"user_id": bob["user"]["id"]}, headers=auth_headers(alice_tokens))
    r = client.post("/v1/friends/requests", json={"user_id": bob["user"]["id"]}, headers=auth_headers(alice_tokens))
    assert r.status_code == 409


def test_auto_accept_reverse_request(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    bob_tokens = login(client, "bob@example.com")
    # Bob already sent Alice a request; Alice sending one auto-accepts.
    client.post("/v1/friends/requests", json={"user_id": alice["user"]["id"]}, headers=auth_headers(bob_tokens))
    r = client.post("/v1/friends/requests", json={"user_id": bob["user"]["id"]}, headers=auth_headers(alice_tokens))
    friends = client.get("/v1/friends", headers=auth_headers(bob_tokens)).json()
    assert len(friends["items"]) == 1


def test_remove_friend(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    make_friends(client, alice_tokens, bob)
    bob_tokens = login(client, "bob@example.com")
    r = client.request("DELETE", "/v1/friends", json={"user_id": bob["user"]["id"]}, headers=auth_headers(alice_tokens))
    assert r.status_code == 200
    friends = client.get("/v1/friends", headers=auth_headers(bob_tokens)).json()
    assert friends["items"] == []


def test_mutual_connections(client):
    # alice is friends with bob AND carol; carol is friends with bob.
    # For carol vs bob, alice is a mutual connection (friend of both).
    a = register_user(client, "alice_m1@example.com", "alicem1")
    b = register_user(client, "bob_m1@example.com", "bobm1")
    c = register_user(client, "carol_m1@example.com", "carolm1")
    # register responses include valid access tokens

    def connect(requester_auth, receiver_auth):
        r = client.post(
            "/v1/friends/requests",
            json={"user_id": receiver_auth["user"]["id"]},
            headers=auth_headers(requester_auth),
        )
        rid = r.json()["request_id"]
        resp = client.post(
            f"/v1/friends/requests/{rid}/respond",
            json={"accept": True},
            headers=auth_headers(receiver_auth),
        )
        assert resp.status_code == 204

    connect(a, b)
    connect(a, c)
    connect(c, b)
    mutuals = client.get(f"/v1/friends/mutual/{b['user']['id']}", headers=auth_headers(c)).json()
    assert any(m["user"]["username"] == "alicem1" for m in mutuals)