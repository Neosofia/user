import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest
from werkzeug.exceptions import NotFound

from src.bootstrap.config import settings

pytestmark = pytest.mark.unit

TENANT = "00000000-0000-7000-8000-000000000001"
USER = "00000000-0000-7000-8000-000000000002"
OTHER = "00000000-0000-7000-8000-000000000003"

OPERATOR_HEADERS = {"X-Active-Role": "operator"}


def _claim(name: str) -> str:
    return f"{settings.jwt_claim_namespace}:{name}"


def _token(rsa_keypair, *, sub: str, roles: list[str], platform_roles: list[str] | None = None):
    claims = {
        "sub": sub,
        "aud": "user",
        "exp": 9999999999,
        "iat": 1,
        _claim("roles"): roles,
    }
    if platform_roles is not None:
        claims[_claim("platform_roles")] = platform_roles
    return jwt.encode(claims, rsa_keypair["private"], algorithm="RS256")


def _sample_user(user_uuid: str = USER) -> dict:
    return {
        "uuid": user_uuid,
        "tenant_uuid": TENANT,
        "idp_id": "user_abc",
        "first_name": "Sam",
        "last_name": "Operator",
        "email": "sam@example.com",
        "platform_roles": ["operator.platform-admin"],
    }


@patch("src.services.user_service.get_user_or_404")
def test_list_users_requires_operator(mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, roles=["clinician"])
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_list_users_operator_jwt_without_registry_row(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.side_effect = NotFound()
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    with patch("src.services.user_service.list_users", return_value=([], 0)):
        token = _token(rsa_keypair, sub=USER, roles=["operator"])
        response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json["total"] == 0


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_list_users_returns_paginated_items(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    with patch("src.services.user_service.list_users", return_value=([_sample_user()], 1)):
        token = _token(rsa_keypair, sub=USER, roles=["operator"])
        response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json["total"] == 1


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_get_user_self_allowed(mock_session, mock_get_user, client, rsa_keypair):
    row = _sample_user()
    mock_get_user.return_value = row
    token = _token(rsa_keypair, sub=USER, roles=["operator"])
    response = client.get(f"/api/v1/users/{USER}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json["uuid"] == USER


@patch("src.services.user_service.get_user_or_404")
def test_get_user_other_allowed_for_operator(mock_get_user, client, rsa_keypair):
    target = _sample_user(OTHER)
    principal = _sample_user(USER)
    principal["platform_roles"] = ["operator.audit-reader"]

    def load_user(user_id: str) -> dict:
        if user_id == USER:
            return principal
        return target

    mock_get_user.side_effect = load_user
    token = _token(rsa_keypair, sub=USER, roles=["operator"])
    response = client.get(f"/api/v1/users/{OTHER}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json["uuid"] == OTHER


def test_list_roles_requires_auth(client):
    assert client.get("/api/v1/roles").status_code == 401


@patch("src.services.user_service.get_user_or_404")
def test_list_roles_allowed_for_clinician(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, roles=["clinician"])
    response = client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {token}", "X-Active-Role": "clinician"},
    )
    assert response.status_code == 200
    assert "clinical.function.staff-nurse" in response.json["platform_roles"]
    assert "operator.platform-admin" not in response.json["platform_roles"]


@patch("src.services.user_service.update_user")
@patch("src.services.user_service.get_user_or_404")
def test_patch_self_as_operator_allows_admin_fields(mock_load_user, mock_update, client, rsa_keypair):
    row = _sample_user()
    mock_load_user.return_value = row
    mock_update.return_value = row
    token = _token(rsa_keypair, sub=USER, roles=["operator"])
    response = client.patch(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
        json={
            "first_name": "Benjamin",
            "platform_roles": ["operator.platform-admin"],
        },
    )
    assert response.status_code == 200
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["self_service"] is False


@patch("src.services.user_service.get_user_or_404")
def test_patch_self_as_clinician_rejects_admin_fields(mock_load_user, client, rsa_keypair):
    row = _sample_user()
    row["platform_roles"] = ["clinical.function.staff-nurse"]
    mock_load_user.return_value = row
    token = _token(rsa_keypair, sub=USER, roles=["clinician"])
    response = client.patch(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}", "X-Active-Role": "clinician"},
        json={"first_name": "Sam", "platform_roles": ["operator.platform-admin"]},
    )
    assert response.status_code == 400
    assert "remove:" in response.json["message"]


@patch("src.services.user_service.get_user_or_404")
def test_patch_rejects_domain_scope_fields(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, roles=["operator"])
    response = client.patch(
        f"/api/v1/users/{OTHER}",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
        json={"site_uuid": TENANT},
    )
    assert response.status_code == 400
    assert "domain services" in response.json["message"]


@patch("src.services.user_service.get_user_or_404")
def test_patch_rejects_immutable_idp_id(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, roles=["operator"])
    response = client.patch(
        f"/api/v1/users/{OTHER}",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
        json={"idp_id": "user_changed"},
    )
    assert response.status_code == 400
    assert "idp_id" in response.json["message"]


@patch("src.services.user_service.get_user_or_404")
def test_list_roles_returns_catalog(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, roles=["operator"])
    response = client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
    )
    assert response.status_code == 200
    assert response.json["assigner_tier1_roles"] == ["operator"]
    assert "operator.platform-admin" in response.json["platform_roles"]
    assert "clinical.function.staff-nurse" not in response.json["platform_roles"]


@patch("src.services.user_service.get_user_or_404")
def test_list_roles_union_for_multi_tier_jwt(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, roles=["operator", "clinician"])
    response = client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {token}", "X-Active-Role": "operator"},
    )
    assert response.status_code == 200
    roles = response.json["platform_roles"]
    assert "operator.platform-admin" in roles
    assert "clinical.function.staff-nurse" in roles
