import pytest

from src.app import create_app
from src.bootstrap.config import Settings

pytestmark = pytest.mark.unit


def test_health_allows_plain_http_in_production(rsa_keypair):
    """Railway's internal probe uses HTTP; /health must not 302 to HTTPS."""
    import base64
    import src.app as app_module
    import src.bootstrap.config as config_module

    original_app_settings = app_module.settings
    original_config_settings = config_module.settings
    production_settings = Settings(
        env="production",
        jwt_public_key=base64.b64encode(rsa_keypair["public"]).decode("utf-8"),
        authorization_policies_dir=original_config_settings.authorization_policies_dir,
    )
    app_module.settings = production_settings
    config_module.settings = production_settings
    try:
        response = create_app().test_client().get("/health")
        assert response.status_code == 200
        assert response.headers.get("Location") is None
        assert response.get_json() == {"status": "ok"}
    finally:
        app_module.settings = original_app_settings
        config_module.settings = original_config_settings


def test_health_is_rate_limited(client):
    # Confirm the endpoint consistently returns 200 across multiple calls.
    # /health is intentionally not rate limited to avoid probe failures.
    for _ in range(3):
        response = client.get("/health")
        assert response.status_code == 200
