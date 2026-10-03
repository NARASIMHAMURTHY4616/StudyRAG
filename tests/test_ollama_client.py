"""Unit tests for OllamaClient including timeouts, streaming, and error handling."""

from unittest.mock import patch, MagicMock
import pytest
import requests
from core.ollama_client import OllamaClient
from config import settings


def test_ollama_is_available():
    client = OllamaClient()
    res = client.is_available()
    assert isinstance(res, bool)


def test_ollama_connection_error():
    client = OllamaClient(base_url="http://localhost:59999", timeout=1)
    with pytest.raises(ConnectionError):
        client.generate("Hello")


@patch("requests.post")
def test_ollama_generate_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "This is a test answer.", "eval_count": 5}
    mock_post.return_value = mock_resp

    client = OllamaClient(base_url="http://localhost:11434")
    answer = client.generate("Test prompt")
    assert answer == "This is a test answer."


@patch("requests.post")
def test_ollama_generate_think_tags_cleaned(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": "<think>Internal thinking...</think>Final clean response.",
        "eval_count": 10,
    }
    mock_post.return_value = mock_resp

    client = OllamaClient(base_url="http://localhost:11434")
    answer = client.generate("Test prompt")
    assert answer == "Final clean response."


@patch("requests.post")
def test_ollama_http_error(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_post.return_value = mock_resp

    client = OllamaClient(base_url="http://localhost:11434")
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("Test prompt")
    assert "HTTP 500" in str(exc_info.value)
