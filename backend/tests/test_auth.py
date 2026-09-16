"""Authentication unit/integration tests."""

from tests.conftest import auth_headers, login, register_user


def test_register_and_login(client):
    res = register_user(client, "ada@example.com", "ada")
    assert res["registered"] is True
    assert res["tokens"]["access_token"]
    assert res["tokens"]["refresh_token"]
    assert res["user"]["username"] == "ada"

    tokens = login(client, "ada@example.com")
    assert tokens["tokens"]["access_token"]


def test_register_duplicate_email_and_username(client):
    register_user(client, "dup@example.com", "duponly")
    r = client.post(
        "/v1/auth/register",
        json={"email": "dup@example.com", "username": "other", "password": "supersecret1", "display_name": "Other"},
    )
    assert r.status_code == 409
    r2 = client.post(
        "/v1/auth/register",
        json={"email": "new@example.com", "username": "duponly", "password": "supersecret1", "display_name": "X"},
    )
    assert r2.status_code == 409


def test_login_bad_password(client):
    register_user(client, "pw@example.com", "pwwrong")
    r = client.post("/v1/auth/login", json={"identifier": "pw@example.com", "password": "nope-nope-1"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "bad_credentials"


def test_login_unknown_identifier(client):
    r = client.post("/v1/auth/login", json={"identifier": "ghost@example.com", "password": "whatever1"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/v1/auth/me")
    assert r.status_code == 401


def test_me(client):
    register_user(client, "me@example.com", "meuser")
    tokens = login(client, "me@example.com")
    r = client.get("/v1/auth/me", headers=auth_headers(tokens))
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"


def test_refresh_token_rotation(client):
    register_user(client, "rot@example.com", "rotate")
    tokens = login(client, "rot@example.com")
    r = client.post("/v1/auth/refresh", json={"refresh_token": tokens["tokens"]["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"] != tokens["tokens"]["access_token"]
    # Old refresh token no longer valid after rotation.
    r2 = client.post("/v1/auth/refresh", json={"refresh_token": tokens["tokens"]["refresh_token"]})
    assert r2.status_code == 401


def test_change_password(client):
    register_user(client, "cp@example.com", "changepw")
    tokens = login(client, "cp@example.com")
    r = client.post(
        "/v1/auth/change-password",
        json={"current_password": "supersecret1", "new_password": "freshsecret1"},
        headers=auth_headers(tokens),
    )
    assert r.status_code == 204
    # Old password rejected, new accepted.
    assert client.post("/v1/auth/login", json={"identifier": "cp@example.com", "password": "supersecret1"}).status_code == 401
    assert client.post("/v1/auth/login", json={"identifier": "cp@example.com", "password": "freshsecret1"}).status_code == 200


def test_password_reset_flow(client):
    register_user(client, "reset@example.com", "resetme")
    # In production the token is emailed; in dev/test it is returned by the service.
    from app.db.session import SessionLocal
    from app.services.auth_service import AuthService

    db = SessionLocal()
    token = AuthService(db).request_password_reset("reset@example.com")
    db.close()
    assert token

    r = client.post("/v1/auth/reset-password", json={"reset_token": token, "password": "brandnew1"})
    assert r.status_code == 204
    assert client.post("/v1/auth/login", json={"identifier": "reset@example.com", "password": "brandnew1"}).status_code == 200


def test_verify_email_flow(client):
    register_user(client, "verify@example.com", "verifyit")
    tokens = login(client, "verify@example.com")
    # issue code via service (production emails it)
    from app.db.session import SessionLocal
    from app.services.auth_service import AuthService

    db = SessionLocal()
    svc = AuthService(db)
    code = svc.issue_email_verification(tokens["user"]["id"])
    db.close()
    r = client.post("/v1/auth/verify-email", json={"code": code}, headers=auth_headers(tokens))
    assert r.status_code == 204


def test_devices_list_and_revoke(client):
    register_user(client, "dev@example.com", "devices")
    tokens = login(client, "dev@example.com")
    devices = client.get("/v1/auth/devices", headers=auth_headers(tokens)).json()
    assert len(devices) == 1
    device_id = devices[0]["id"]
    r = client.delete(f"/v1/auth/devices/{device_id}", headers=auth_headers(tokens))
    assert r.status_code == 204


def test_delete_account(client):
    register_user(client, "del@example.com", "deleteit")
    tokens = login(client, "del@example.com")
    r = client.request(
        "DELETE",
        "/v1/auth/account",
        json={"password": "supersecret1", "confirmation": "DELETE"},
        headers=auth_headers(tokens),
    )
    assert r.status_code == 204
    assert client.post("/v1/auth/login", json={"identifier": "del@example.com", "password": "supersecret1"}).status_code == 401


def test_logout_revokes_refresh(client):
    register_user(client, "lo@example.com", "logoutuser")
    tokens = login(client, "lo@example.com")
    r = client.post("/v1/auth/logout", json={}, headers=auth_headers(tokens))
    assert r.status_code == 204
    assert client.post("/v1/auth/refresh", json={"refresh_token": tokens["tokens"]["refresh_token"]}).status_code == 401