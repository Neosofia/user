import pytest
from flask import g

from authorization_in_the_middle.entities import ID_PLACEHOLDER
from authorization_in_the_middle.flask_identity import principal_cedar_attrs
from authorization_in_the_middle.rest_defaults import synthesize_member_builder, synthesize_write_builder

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


def test_principal_cedar_attrs_use_jwt_short_roles():
    claims = {
        "sub": USER,
        _claim("actors"): ["operator"],
        _claim("roles"): ["admin"],
        _claim("tenant_type"): "platform",
        _claim("tenant_uuid"): TENANT,
    }
    attrs = principal_cedar_attrs(
        claims,
        actor_classes=entities.tier1_actor_classes(),
    )
    assert attrs["roles"] == ["admin"]
    assert attrs["tenantType"] == "platform"
    assert attrs["tenantId"] == TENANT
    assert attrs["isOperator"] is True


def test_synthesized_member_builder_uses_registry_attrs():
    builder = synthesize_member_builder(
        namespace=entities.NAMESPACE,
        model_name="user",
        id_arg="user_uuid",
        entities_mod=entities,
    )
    patient = {
        "uuid": PATIENT,
        "tenant_uuid": TENANT,
        "roles": ["patient.self"],
    }
    entity = builder(PATIENT, patient)
    assert entity["attrs"]["roles"] == ["patient.self"]
    assert entity["attrs"]["tenantId"] == TENANT


def test_resolve_principal_uses_jwt_claims(app):
    with app.test_request_context("/"):
        g.jwt_claims = {
            "sub": USER,
            _claim("actors"): ["operator"],
            _claim("roles"): ["admin"],
            _claim("tenant_type"): "platform",
            _claim("tenant_uuid"): TENANT,
        }
        entity = entities.resolve_principal()
    assert entity["uid"]["__entity"]["id"] == USER
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


def test_synthesized_write_builder_resolves_placeholder_uuid():
    builder = synthesize_write_builder(
        namespace=entities.NAMESPACE,
        model_name="user",
        id_arg="user_uuid",
        entities_mod=entities,
    )
    record = {
        "uuid": ID_PLACEHOLDER,
        "tenant_uuid": TENANT,
        "roles": ["patient.self"],
    }
    entity = builder(record)
    assert entity["attrs"]["roles"] == ["patient.self"]
