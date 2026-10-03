"""Integration tests for chat streaming endpoint."""

import json
import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_chat_stream_empty_question(client):
    res = client.post("/api/chat/stream", json={"question": ""})
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


def test_chat_stream_headers_and_events(client):
    res = client.post(
        "/api/chat/stream",
        json={"question": "Hello", "top_k": 4},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["Content-Type"]
    assert res.headers.get("Cache-Control") == "no-cache"
    assert res.headers.get("X-Accel-Buffering") == "no"

    # Read SSE events
    body = res.get_data(as_text=True)
    assert "data: " in body
    assert "conversation_id" in body
