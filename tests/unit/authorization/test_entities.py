from unittest.mock import patch

import pytest
from flask import g
from werkzeug.exceptions import NotFound

from authorization_in_the_middle.entities import ID_PLACEHOLDER

from src.authorization import entities
from src.bootstrap.config import settings

pytestmark = pytest.mark.unit

TENANT = "00000000-0000-7000-8000-000000000001"
USER = "00000000-0000-7000-8000-000000000002"
PATIENT = "00000000-0000-7000-8000-000000000099"


def _claim(name: str) -> str:
    return f"{settings.jwt_claim_namespace}:{name}"


def test_registry_user_cedar_attrs_keep_full_role_slugs():
    row = {
        "uuid": PATIENT,
        "tenant_uuid": TENANT,
        "roles": ["patient.self"],
    }
    attrs = entities.registry_user_cedar_attrs(row)
    assert attrs["roles"] == ["patient.self"]
    assert attrs["tenantId"] == TENANT
    assert attrs["tokenType"] == "human"


def test_principal_cedar_attrs_use_jwt_short_roles(app):
    row = {"uuid": USER, "tenant_uuid": TENANT, "roles": ["platform.admin"]}
    claims = {
        "sub": USER,
        _claim("actors"): ["operator"],
        _claim("roles"): ["admin"],
        _claim("tenant_type"): "platform",
    }
    attrs = entities.principal_cedar_attrs(row, claims)
    assert attrs["roles"] == ["admin"]
    assert attrs["tenantType"] == "platform"
    assert attrs["isOperator"] is True


def test_build_user_resource_entity_uses_registry_row():
    patient = {
        "uuid": PATIENT,
        "tenant_uuid": TENANT,
        "roles": ["patient.self"],
    }
    entity = entities.build_user_resource_entity(PATIENT, patient)
    assert entity["attrs"]["roles"] == ["patient.self"]
    assert entity["attrs"]["tenantId"] == TENANT


@patch(
    "src.services.user_service.get_user_or_404",
    return_value={"uuid": USER, "tenant_uuid": TENANT, "roles": ["platform.admin"]},
)
def test_resolve_principal_uses_registry_row(mock_get_user, app):
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": USER,
            _claim("actors"): ["operator"],
            _claim("roles"): ["admin"],
            _claim("tenant_type"): "platform",
        }
        entity = entities.resolve_principal()
    assert entity["attrs"]["roles"] == ["admin"]
    assert entity["attrs"]["tenantId"] == TENANT
    assert entity["attrs"]["isOperator"] is True


def test_resolve_principal_service_token(app):
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": "authentication",
            "token_type": "service",
        }
        entity = entities.resolve_principal()
    assert entity["uid"]["__entity"]["type"] == f"{entities.NAMESPACE}::Service"
    assert entity["attrs"]["serviceSlug"] == "authentication"


@patch("src.services.user_service.get_user_or_404", side_effect=NotFound())
def test_resolve_principal_falls_back_when_registry_row_missing(mock_get_user, app):
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": USER,
            _claim("tenant_uuid"): TENANT,
            _claim("actors"): ["patient"],
        }
        entity = entities.resolve_principal()
    assert entity["attrs"]["tenantId"] == TENANT
    assert entity["attrs"]["isPatient"] is True


def test_build_write_user_entity_resolves_placeholder_uuid():
    record = {
        "uuid": ID_PLACEHOLDER,
        "tenant_uuid": TENANT,
        "roles": ["patient.self"],
    }
    entity = entities.build_write_user_entity(record)
    assert entity["attrs"]["roles"] == ["patient.self"]
