import pytest

from src.app import create_app

pytestmark = pytest.mark.unit


def test_http_error_handler_returns_json_shape(client):
    response = client.post("/health")
    assert response.status_code == 405
    assert response.get_json() == {"error": "method_not_allowed"}


def test_unhandled_error_handler_returns_500():
    app = create_app({"TESTING": True, "TIER1_ACTOR_CLASSES": frozenset({"operator"})})

    @app.get("/test-unhandled-error")
    def _boom():
        raise RuntimeError("test failure")

    with app.test_client() as client:
        response = client.get("/test-unhandled-error")
    assert response.status_code == 500
    assert response.get_json() == {"error": "internal_server_error"}
