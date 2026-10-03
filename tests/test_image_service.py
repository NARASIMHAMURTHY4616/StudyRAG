"""Unit tests for ImageService and backend status checks."""

from visual_learning.image_service import ImageService
from visual_learning.image_backends import NullImageBackend, get_image_backend


def test_null_image_backend_status():
    backend = NullImageBackend()
    assert backend.is_available() is False

    status = backend.get_status()
    assert status["available"] is False
    assert status["backend"] == "none"
    assert "optional and disabled" in status["message"]


def test_null_image_backend_generate_returns_unavailable():
    backend = NullImageBackend()
    result = backend.generate_image("A futuristic network diagram")
    assert result.status == "unavailable"
    assert result.backend == "none"
    assert "not configured" in result.error


def test_image_service_empty_prompt():
    service = ImageService()
    res = service.generate_illustration("")
    assert res.status == "error"
    assert "cannot be empty" in res.error


def test_factory_get_image_backend():
    b_none = get_image_backend("none")
    assert isinstance(b_none, NullImageBackend)

    b_unknown = get_image_backend("unknown_backend_xyz")
    assert isinstance(b_unknown, NullImageBackend)
