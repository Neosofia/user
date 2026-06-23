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
    assert "/api/v1/users/{user_uuid}" in spec["paths"]
    assert "/api/v1/tenants/{tenant_uuid}/users" in spec["paths"]
    assert "/api/v1/roles" in spec["paths"]


def test_openapi_spec_defines_error_schema():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    error_schema = spec["components"]["schemas"]["ErrorResponse"]
    assert error_schema["required"] == ["error"]
    error_codes = error_schema["properties"]["error"]["enum"]
    assert "forbidden" in error_codes
    assert "authorization_unavailable" in error_codes


def test_openapi_operation_ids_are_unique():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    operation_ids: list[str] = []
    for path_item in spec["paths"].values():
        for method, operation in path_item.items():
            if method.startswith("x") or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if operation_id:
                operation_ids.append(operation_id)

    assert len(operation_ids) == len(set(operation_ids))


def test_openapi_platform_user_list_supports_pagination_query():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    params = spec["paths"]["/api/v1/users"]["get"]["parameters"]
    names = {param["name"] for param in params}
    assert {"page", "page_size", "q"}.issubset(names)


def test_openapi_user_audits_support_pagination_query():
    root = Path(__file__).resolve().parents[3]
    spec = json.loads((root / "openapi.json").read_text())

    params = spec["paths"]["/api/v1/users/{user_uuid}/audits"]["get"]["parameters"]
    names = {param["name"] for param in params}
    assert {"page", "page_size"}.issubset(names)
