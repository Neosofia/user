import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_openapi_spec_contains_core_paths():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    assert spec["openapi"] == "3.0.3"
    assert "/health" in spec["paths"]
    assert "/api/v1/users" in spec["paths"]
    assert "/api/v1/users/{user_id}" in spec["paths"]
    assert "/api/v1/roles" in spec["paths"]


def test_openapi_spec_defines_error_schema():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    error_schema = spec["components"]["schemas"]["ErrorResponse"]
    assert error_schema["required"] == ["error"]
    error_codes = error_schema["properties"]["error"]["enum"]
    assert "forbidden" in error_codes
    assert "authorization_unavailable" in error_codes
