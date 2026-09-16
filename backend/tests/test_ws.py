"""WebSocket integration tests. Contract: first message must be `subscribe`."""

from tests.conftest import auth_headers


def _receive_until(ws, want: str):
    import time

    for _ in range(10):
        msg = ws.receive_json()
        if msg.get("type") == want:
            return msg
        time.sleep(0.05)
    raise AssertionError(f"no '{want}' message received")


def test_connect_subscribe_and_heartbeat(client, two_friends):
    alice, bob = two_friends
    with client.websocket_connect(f"/v1/ws?token={alice['tokens']['access_token']}") as ws:
        ws.send_json({"type": "subscribe", "conversation_ids": ["abc"]})
        assert _receive_until(ws, "subscribed")["type"] == "subscribed"
        ws.send_json({"type": "heartbeat"})
        ack = _receive_until(ws, "heartbeat_ack")
        assert ack["type"] == "heartbeat_ack"


def test_unknown_event_returns_error(client, two_friends):
    alice, bob = two_friends
    with client.websocket_connect(f"/v1/ws?token={alice['tokens']['access_token']}") as ws:
        ws.send_json({"type": "subscribe", "conversation_ids": []})
        _receive_until(ws, "subscribed")
        ws.send_json({"type": "bogus.event"})
        resp = _receive_until(ws, "error")
        assert resp["type"] == "error"


def test_subscribe_response_lists_ids(client, two_friends):
    alice, bob = two_friends
    with client.websocket_connect(f"/v1/ws?token={alice['tokens']['access_token']}") as ws:
        ws.send_json({"type": "subscribe", "conversation_ids": ["abc", "def"]})
        resp = _receive_until(ws, "subscribed")
        assert resp["type"] == "subscribed"
        assert set(resp["conversation_ids"]) == {"abc", "def"}


def test_typing_signal_does_not_error(client, two_friends):
    alice, bob = two_friends
    conv = client.post(
        "/v1/conversations",
        json={"user_id": bob["user"]["id"]},
        headers=auth_headers(alice),
    ).json()
    cid = conv["id"]
    with client.websocket_connect(f"/v1/ws?token={bob['tokens']['access_token']}") as bob_ws:
        bob_ws.send_json({"type": "subscribe", "conversation_ids": [cid]})
        _receive_until(bob_ws, "subscribed")
        with client.websocket_connect(f"/v1/ws?token={alice['tokens']['access_token']}") as alice_ws:
            alice_ws.send_json({"type": "subscribe", "conversation_ids": [cid]})
            _receive_until(alice_ws, "subscribed")
            alice_ws.send_json({"type": "typing.started", "conversation_id": cid})
            import time; time.sleep(0.2)
            bob_ws.send_json({"type": "heartbeat"})
            ack = _receive_until(bob_ws, "heartbeat_ack")
            assert ack["type"] == "heartbeat_ack"