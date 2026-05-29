import pytest

pytestmark = pytest.mark.integration


def test_health_endpoint(client, api_spec, validate_response):
    response = client.get("/health", base_url="https://localhost")

    assert response.status_code == 200
    validate_response(api_spec, "/health", "get", 200, response.get_json())
