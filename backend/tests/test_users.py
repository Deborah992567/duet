"""User/profile/search/block tests."""

from tests.conftest import auth_headers, login, register_user


def test_update_profile(client):
    register_user(client, "profile@example.com", "profile1")
    tokens = login(client, "profile@example.com")
    r = client.patch(
        "/v1/users/me",
        json={"display_name": "Profile One", "bio": "Hello there", "theme": "dark"},
        headers=auth_headers(tokens),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["display_name"] == "Profile One"


def test_username_conflict(client):
    register_user(client, "u1@example.com", "thereal")
    register_user(client, "u2@example.com", "someone")
    tokens = login(client, "u2@example.com")
    r = client.patch("/v1/users/me", json={"username": "thereal"}, headers=auth_headers(tokens))
    assert r.status_code == 409


def test_search_users(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    r = client.get("/v1/users/search", params={"q": "bob"}, headers=auth_headers(alice_tokens))
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(u["username"] == "bob" for u in items)


def test_get_public_user_visibility(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    r = client.get(f"/v1/users/{bob['user']['id']}", headers=auth_headers(alice_tokens))
    assert r.status_code == 200
    assert r.json()["username"] == "bob"


def test_get_public_user_hidden_when_private(client, two_users):
    alice, bob = two_users
    # Alice hides her profile from non-friends.
    alice_tokens = login(client, "alice@example.com")
    client.patch(
        "/v1/users/me/privacy",
        json={"profile_visibility": "nobody"},
        headers=auth_headers(alice_tokens),
    )
    bob_tokens = login(client, "bob@example.com")
    r = client.get(f"/v1/users/{alice['user']['id']}", headers=auth_headers(bob_tokens))
    assert r.status_code == 404


def test_block_and_unblock(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    r = client.post(f"/v1/users/{bob['user']['id']}/block", headers=auth_headers(alice_tokens))
    assert r.status_code == 204
    blocked = client.get("/v1/users/blocked/list", headers=auth_headers(alice_tokens)).json()
    assert len(blocked) == 1
    r2 = client.request("DELETE", f"/v1/users/{bob['user']['id']}/block", headers=auth_headers(alice_tokens))
    assert r2.status_code == 204
    blocked_after = client.get("/v1/users/blocked/list", headers=auth_headers(alice_tokens)).json()
    assert len(blocked_after) == 0


def test_block_removes_friend_visibility(client, two_users):
    alice, bob = two_users
    alice_tokens = login(client, "alice@example.com")
    # Bob and Alice become friends first via friend request flow (covered by friends suite)
    from tests.test_friends import make_friends

    make_friends(client, alice_tokens, bob)
    bob_tokens = login(client, "bob@example.com")
    friends = client.get("/v1/friends", headers=auth_headers(bob_tokens)).json()
    assert len(friends["items"]) == 1
    client.post(f"/v1/users/{bob['user']['id']}/block", headers=auth_headers(alice_tokens))
    friends_after = client.get("/v1/friends", headers=auth_headers(bob_tokens)).json()
    assert len(friends_after["items"]) == 0