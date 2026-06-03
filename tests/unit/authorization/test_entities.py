from unittest.mock import patch

import pytest
from flask import g

from src.authorization import entities
from src.bootstrap.config import settings

pytestmark = pytest.mark.unit

TENANT = "00000000-0000-7000-8000-000000000001"
USER = "00000000-0000-7000-8000-000000000002"


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
