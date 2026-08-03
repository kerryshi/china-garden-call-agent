"""Demo webapp API: thin HTTP layer over DialogSession. No core logic here."""

import pytest
from fastapi.testclient import TestClient

from china_garden.web import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def start_session(client: TestClient) -> dict:
    resp = client.post("/api/session")
    assert resp.status_code == 200
    return resp.json()


def say(client: TestClient, session_id: str, utterance: str) -> dict:
    resp = client.post("/api/chat", json={"session_id": session_id, "utterance": utterance})
    assert resp.status_code == 200
    return resp.json()


def test_session_create_returns_greeting_and_restaurant(client):
    data = start_session(client)
    assert data["session_id"]
    assert "automated assistant" in data["greeting"]
    assert data["restaurant"]["name"] == "China Garden"
    assert data["restaurant"]["phone"]
    assert data["restaurant"]["address"]


def test_full_order_flow_via_api(client):
    sid = start_session(client)["session_id"]

    turn = say(client, sid, "two egg rolls please")
    assert turn["state"] == "ORDERING"
    assert not turn["done"]
    assert turn["ticket"] is None
    assert len(turn["order"]) == 1
    assert turn["order"][0]["qty"] == 2
    assert turn["totals"]["total_cents"] > 0

    turn = say(client, sid, "that's it")
    assert turn["state"] == "READ_BACK"
    assert "read that back" in turn["reply"]

    turn = say(client, sid, "yes, that's right")
    assert turn["state"] == "CONFIRMED"
    assert turn["done"]
    assert "PICKUP ORDER" in turn["ticket"]
    assert "TOTAL" in turn["ticket"]
    # the spoken reply must not contain the ticket art - TTS would read it aloud
    assert "PICKUP ORDER" not in turn["reply"]
    assert "ready for pickup" in turn["reply"]


def test_order_snapshot_updates_each_turn(client):
    sid = start_session(client)["session_id"]
    turn = say(client, sid, "one general tso's chicken")
    assert [line["qty"] for line in turn["order"]] == [1]
    line = turn["order"][0]
    assert line["item"] and "line_total_cents" in line
    totals = turn["totals"]
    assert totals["subtotal_cents"] + totals["tax_cents"] == totals["total_cents"]


def test_handoff_sets_flag(client):
    sid = start_session(client)["session_id"]
    turn = say(client, sid, "can I talk to a person")
    assert turn["handoff"]
    assert turn["done"]
    assert turn["state"] == "HANDOFF"


def test_unknown_session_is_404(client):
    resp = client.post("/api/chat", json={"session_id": "nope", "utterance": "hi"})
    assert resp.status_code == 404


def test_index_serves_demo_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "caller-panel" in resp.text
