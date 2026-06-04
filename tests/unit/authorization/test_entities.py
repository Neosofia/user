from unittest.mock import patch

import pytest
from flask import g
from werkzeug.exceptions import NotFound

from src.authorization import entities
from src.bootstrap.config import settings

pytestmark = pytest.mark.unit

TENANT = "00000000-0000-7000-8000-000000000001"
USER = "00000000-0000-7000-8000-000000000002"
PATIENT = "00000000-0000-7000-8000-000000000099"


def _claim(name: str) -> str:
    return f"{settings.jwt_claim_namespace}:{name}"


def test_principal_actors_prefers_session_actors(app):
    claims = {
        "sub": USER,
        _claim("actors"): ["operator", "clinician"],
        _claim("session_actors"): ["clinician"],
    }
    with app.test_request_context("/"):
        g.jwt_claims = claims
        assert entities.principal_actors() == ["clinician"]


@patch("src.services.user_service.get_user_or_404", return_value={"tenant_uuid": TENANT})
def test_principal_tenant_uuid_from_registry(mock_get_user, app):
    with app.test_request_context("/"):
        g.jwt_claims = {"sub": USER}
        assert entities.principal_tenant_uuid() == TENANT


def test_tenant_type_for_study_uses_org_role_header(app):
    with app.test_request_context("/", headers={"X-Active-Org-Role": "cro.acme"}):
        g.jwt_claims = {"sub": USER, _claim("actors"): ["study"]}
        assert entities.tenant_type_for_row({"roles": ["cro.acme"]}) == "cro"


def test_tenant_type_prefers_registry_roles_over_jwt_claim(app):
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": USER,
            _claim("tenant_type"): "platform",
            _claim("actors"): ["clinician"],
        }
        assert entities.tenant_type_for_row({"roles": ["patient.self"]}) == "patient"


def test_resource_entity_uses_registry_roles_not_jwt(app):
    """Target user Cedar attrs must come from the row, not the caller JWT roles."""
    patient = {
        "uuid": PATIENT,
        "tenant_uuid": TENANT,
        "roles": ["patient.self"],
    }
    claims = {
        "sub": USER,
        _claim("actors"): ["clinician"],
        _claim("roles"): ["site.clinical"],
        _claim("tenant_type"): "site",
    }
    with app.test_request_context("/"):
        g.jwt_claims = claims
        entity = entities.build_user_resource_entity(PATIENT, patient, claims)
    assert entity["attrs"]["roles"] == ["self"]
    assert entity["attrs"]["tenantType"] == "patient"


def test_principal_entity_prefers_jwt_roles_over_registry_row(app):
    row = {"uuid": USER, "tenant_uuid": TENANT, "roles": []}
    claims = {
        "sub": USER,
        _claim("actors"): ["operator"],
        _claim("roles"): ["platform.admin"],
        _claim("tenant_type"): "platform",
    }
    with app.test_request_context("/"):
        g.jwt_claims = claims
        entity = entities.build_principal_entity(row, claims)
    assert entity["attrs"]["roles"] == ["admin"]


def test_principal_tenant_uuid_prefers_jwt_claim(app):
    with app.test_request_context("/"):
        g.jwt_claims = {"sub": USER, _claim("tenant_uuid"): TENANT}
        assert entities.principal_tenant_uuid() == TENANT


def test_principal_tenant_uuid_service_token_returns_none(app):
    with app.test_request_context("/"):
        g.jwt_claims = {"sub": "svc", _claim("token_type"): "service"}
        assert entities.principal_tenant_uuid() is None


@patch("src.services.user_service.get_user_or_404", side_effect=NotFound())
def test_principal_tenant_uuid_missing_registry_row(mock_get_user, app):
    with app.test_request_context("/"):
        g.jwt_claims = {"sub": USER}
        assert entities.principal_tenant_uuid() is None


def test_claims_requires_sub(app):
    with app.test_request_context("/"):
        g.jwt_claims = {}
        with pytest.raises(ValueError, match="missing sub"):
            entities._claims()


def test_tenant_type_falls_back_to_jwt_claim(app):
    with app.test_request_context("/"):
        g.jwt_claims = {"sub": USER, _claim("tenant_type"): "site"}
        assert entities.tenant_type_for_row({"roles": []}) == "site"


def test_study_tenant_type_from_registry_role_without_header(app):
    with app.test_request_context("/"):
        g.jwt_claims = {"sub": USER, _claim("actors"): ["study"]}
        assert entities.tenant_type_for_row({"roles": ["sponsor.acme"]}) == "sponsor"


def test_study_context_invalid_slug_returns_platform_tenant_type(app):
    with app.test_request_context("/"):
        g.jwt_claims = {"sub": USER, _claim("actors"): ["study"]}
        assert entities.tenant_type_for_row({"roles": ["sponsor"]}) == "platform"


def test_active_org_role_header_ignored_without_dot(app):
    with app.test_request_context("/", headers={"X-Active-Org-Role": "invalid"}):
        g.jwt_claims = {"sub": USER, _claim("actors"): ["study"]}
        assert entities.tenant_type_for_row({"roles": ["cro.acme"]}) == "cro"


def test_operator_tenant_type_uses_platform_org_role_header(app):
    row = {
        "uuid": USER,
        "tenant_uuid": TENANT,
        "roles": ["site.clinical", "platform.admin", "patient.self"],
    }
    claims = {
        "sub": USER,
        _claim("actors"): ["operator"],
        _claim("roles"): ["admin"],
        _claim("tenant_type"): "platform",
    }
    with app.test_request_context(
        "/",
        headers={"X-Active-Org-Role": "platform.admin", "X-Active-Actor": "operator"},
    ):
        g.jwt_claims = claims
        entity = entities.build_principal_entity(row, claims)
    assert entity["attrs"]["tenantType"] == "platform"
    assert entity["attrs"]["roles"] == ["admin"]
    assert entity["attrs"]["isOperator"] is True


def test_operator_tenant_type_finds_platform_role_when_not_first_in_row(app):
    row = {
        "uuid": USER,
        "tenant_uuid": TENANT,
        "roles": ["site.clinical", "platform.admin"],
    }
    claims = {
        "sub": USER,
        _claim("actors"): ["operator"],
        _claim("roles"): [],
        _claim("tenant_type"): "platform",
    }
    with app.test_request_context("/", headers={"X-Active-Actor": "operator"}):
        g.jwt_claims = claims
        entity = entities.build_principal_entity(row, claims)
    assert entity["attrs"]["tenantType"] == "platform"
    assert entity["attrs"]["roles"] == ["admin"]


def test_clinician_tenant_type_uses_site_org_role_header(app):
    row = {
        "uuid": USER,
        "tenant_uuid": TENANT,
        "roles": ["platform.admin", "site.clinical"],
    }
    claims = {
        "sub": USER,
        _claim("actors"): ["clinician"],
        _claim("roles"): ["clinical"],
        _claim("tenant_type"): "site",
    }
    with app.test_request_context(
        "/",
        headers={"X-Active-Org-Role": "site.clinical", "X-Active-Actor": "clinician"},
    ):
        g.jwt_claims = claims
        entity = entities.build_principal_entity(row, claims)
    assert entity["attrs"]["tenantType"] == "site"
    assert entity["attrs"]["roles"] == ["clinical"]
