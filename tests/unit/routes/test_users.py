import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest
from werkzeug.exceptions import NotFound

from src.bootstrap.config import settings
from src.routes import users as user_routes

pytestmark = pytest.mark.unit

TENANT = "00000000-0000-7000-8000-000000000001"
USER = "00000000-0000-7000-8000-000000000002"
OTHER = "00000000-0000-7000-8000-000000000003"

OPERATOR_HEADERS = {"X-Active-Actor": "operator"}


def _claim(name: str) -> str:
    return f"{settings.jwt_claim_namespace}:{name}"


def _token(
    rsa_keypair,
    *,
    sub: str,
    actors: list[str],
    tenant_type: str = "platform",
    roles: list[str] | None = None,
):
    claims = {
        "sub": sub,
        "aud": "user",
        "exp": 9999999999,
        "iat": 1,
        _claim("actors"): actors,
        _claim("tenant_type"): tenant_type,
    }
    if roles is not None:
        claims[_claim("roles")] = roles
    return jwt.encode(claims, rsa_keypair["private"], algorithm="RS256")




def _admin_token(rsa_keypair, *, sub: str = USER):
    return _token(
        rsa_keypair,
        sub=sub,
        actors=["operator"],
        tenant_type="platform",
        roles=["admin"],
    )

def _service_token(rsa_keypair, *, sub: str = "authentication"):
    claims = {
        "sub": sub,
        "aud": "user",
        "exp": 9999999999,
        "iat": 1,
        _claim("token_type"): "service",
    }
    return jwt.encode(claims, rsa_keypair["private"], algorithm="RS256")


def _sample_user(user_uuid: str = USER) -> dict:
    return {
        "uuid": user_uuid,
        "tenant_uuid": TENANT,
        "idp_id": "user_abc",
        "first_name": "Sam",
        "last_name": "Operator",
        "email": "sam@example.com",
        "roles": ["platform.admin"],
    }


@patch("src.services.user_service.get_user_or_404")
def test_list_users_requires_operator(mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_list_users_operator_jwt_without_registry_row(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.side_effect = NotFound()
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    with patch("src.services.user_service.list_users", return_value=([], 0)):
        token = _token(rsa_keypair, sub=USER, actors=["operator"])
        response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_list_users_returns_paginated_items(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    with patch("src.services.user_service.list_users", return_value=([_sample_user()], 1)):
        token = _token(rsa_keypair, sub=USER, actors=["operator"])
        response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json["total"] == 1


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_get_user_self_allowed(mock_session, mock_get_user, client, rsa_keypair):
    row = _sample_user()
    mock_get_user.return_value = row
    token = _token(rsa_keypair, sub=USER, actors=["operator"])
    response = client.get(f"/api/v1/users/{USER}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json["uuid"] == USER


@patch("src.services.user_service.get_user_or_404")
def test_get_user_other_allowed_for_platform_admin(mock_get_user, client, rsa_keypair):
    target = _sample_user(OTHER)
    principal = _sample_user(USER)
    principal["roles"] = ["platform.admin"]

    def load_user(user_id: str) -> dict:
        if user_id == USER:
            return principal
        return target

    mock_get_user.side_effect = load_user
    token = _token(rsa_keypair, sub=USER, actors=["operator"])
    response = client.get(f"/api/v1/users/{OTHER}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json["uuid"] == OTHER


def test_list_roles_requires_auth(client):
    assert client.get("/api/v1/roles").status_code == 401


@patch("src.services.user_service.get_user_or_404")
def test_list_roles_allowed_for_clinician(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
    )
    assert response.status_code == 200
    assert "site.clinical" in response.json["roles"]
    assert "platform.admin" not in response.json["roles"]


@patch("src.services.user_service.update_user")
@patch("src.services.user_service.get_user_or_404")
def test_patch_accepts_cross_tenant_type_roles_for_platform_user(
    mock_load_user, mock_update, client, rsa_keypair
):
    row = _sample_user()
    mock_load_user.return_value = row
    updated = {
        **row,
        "roles": [
            "platform.admin",
            "cro.clinical-ops",
            "patient.self",
            "site.clinical",
            "smo.readonly",
        ],
    }
    mock_update.return_value = updated
    token = _token(
        rsa_keypair,
        sub=USER,
        actors=["operator", "clinician", "patient"],
        tenant_type="platform",
    )
    response = client.patch(
        f"/api/v1/users/{OTHER}",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
        json={"roles": updated["roles"]},
    )
    assert response.status_code == 200
    mock_update.assert_called_once()


@patch("src.services.user_service.update_user")
@patch("src.services.user_service.get_user_or_404")
def test_patch_self_as_operator_allows_admin_fields(mock_load_user, mock_update, client, rsa_keypair):
    row = _sample_user()
    mock_load_user.return_value = row
    mock_update.return_value = row
    token = _token(rsa_keypair, sub=USER, actors=["operator"])
    response = client.patch(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
        json={
            "first_name": "Benjamin",
            "roles": ["platform.admin"],
        },
    )
    assert response.status_code == 200
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["self_service"] is False


@patch("src.services.user_service.get_user_or_404")
def test_patch_self_as_clinician_rejects_admin_fields(mock_load_user, client, rsa_keypair):
    row = _sample_user()
    row["roles"] = ["site.clinical"]
    mock_load_user.return_value = row
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.patch(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
        json={"first_name": "Sam", "roles": ["platform.admin"]},
    )
    assert response.status_code == 400
    assert "remove:" in response.json["message"]


@patch("src.services.user_service.get_user_or_404")
def test_patch_rejects_domain_scope_fields(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["operator"])
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
    token = _token(rsa_keypair, sub=USER, actors=["operator"])
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
    token = _token(rsa_keypair, sub=USER, actors=["operator"])
    response = client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
    )
    assert response.status_code == 200
    assert response.json["assigner_actors"] == ["operator"]
    assert "platform.admin" in response.json["roles"]
    assert "site.clinical" not in response.json["roles"]
    assert response.json["assigner_actor_prefixes"] == {
        "operator": ["platform.", "cro.", "sponsor.", "smo."],
    }


@patch("src.services.user_service.get_user_or_404")
def test_list_roles_union_for_multi_tier_jwt(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["operator", "clinician"])
    response = client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "operator"},
    )
    assert response.status_code == 200
    roles = response.json["roles"]
    assert "platform.admin" in roles
    assert "site.clinical" in roles


@patch("src.services.user_service.provision_user_identity")
@patch("src.routes.users.SessionLocal")
def test_provision_put_accepts_authentication_service_token(
    mock_session,
    mock_provision,
    client,
    rsa_keypair,
):
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    mock_provision.return_value = (_sample_user(), True)
    token = _service_token(rsa_keypair)

    response = client.put(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "tenant_uuid": TENANT,
            "idp_id": "user_abc",
            "first_name": "Sam",
            "last_name": "Operator",
            "email": "sam@example.com",
        },
    )

    assert response.status_code == 201
    mock_provision.assert_called_once_with(
        mock_db,
        USER,
        {
            "tenant_uuid": TENANT,
            "idp_id": "user_abc",
            "first_name": "Sam",
            "last_name": "Operator",
            "email": "sam@example.com",
        },
    )


@patch("src.services.user_service.get_user_or_404")
def test_provision_put_rejects_human_token(mock_load_user, client, rsa_keypair):
    mock_load_user.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["operator"])

    response = client.put(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
        json={
            "tenant_uuid": TENANT,
            "idp_id": "user_abc",
            "first_name": "Sam",
            "last_name": "Operator",
            "email": "sam@example.com",
        },
    )

    assert response.status_code == 403


def test_provision_put_validates_required_fields(client, rsa_keypair):
    token = _service_token(rsa_keypair)

    response = client.put(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_uuid": TENANT},
    )

    assert response.status_code == 400
    assert "missing required fields" in response.json["message"]


def test_validate_update_payload_branch_errors():
    assert user_routes._validate_update_payload({}, self_service=False) == "empty body"
    assert "tenant_uuid" in user_routes._validate_update_payload(
        {"tenant_uuid": "not-a-uuid"},
        self_service=False,
    )


def test_validate_provision_payload_branch_errors():
    valid = {
        "tenant_uuid": TENANT,
        "idp_id": "user_abc",
        "first_name": "Sam",
        "last_name": "Operator",
        "email": "sam@example.com",
    }
    assert user_routes._validate_provision_payload("not-a-uuid", valid) == "user_id must be a UUID"
    assert "unsupported fields" in user_routes._validate_provision_payload(
        USER,
        {**valid, "roles": []},
    )
    assert user_routes._validate_provision_payload(
        USER,
        {**valid, "tenant_uuid": "not-a-uuid"},
    ) == "tenant_uuid must be a UUID"
    assert user_routes._validate_provision_payload(USER, {**valid, "idp_id": ""}) == "idp_id is required"
    assert "email" in user_routes._validate_provision_payload(USER, {**valid, "email": 123})
    assert user_routes._validate_provision_payload(USER, {**valid, "actors": ["operator"]}) is None
    assert user_routes._validate_provision_payload(USER, {**valid, "actors": "operator"}) == (
        "actors must be an array of strings"
    )


@patch("src.services.user_service.get_user_audits")
@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_get_user_audits_route_returns_items(
    mock_session,
    mock_get_user,
    mock_get_audits,
    client,
    rsa_keypair,
):
    mock_get_user.return_value = _sample_user()
    mock_session.return_value.__enter__.return_value = MagicMock()
    mock_get_audits.return_value = ([], 0)
    token = _token(rsa_keypair, sub=USER, actors=["operator"])

    response = client.get(
        f"/api/v1/users/{OTHER}/audits",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
    )

    assert response.status_code == 200
    assert response.json["user_uuid"] == OTHER


@patch("src.services.user_service.get_user_audits")
@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_get_user_audits_allows_jwt_org_role_slugs(
    mock_session,
    mock_get_user,
    mock_get_audits,
    client,
    rsa_keypair,
):
    principal = _sample_user(USER)
    target = _sample_user(OTHER)

    def load_user(user_id: str) -> dict:
        return principal if user_id == USER else target

    mock_get_user.side_effect = load_user
    mock_session.return_value.__enter__.return_value = MagicMock()
    mock_get_audits.return_value = ([{"history_uuid": str(uuid.uuid4()), "change_type": 2}], 1)
    token = _token(
        rsa_keypair,
        sub=USER,
        actors=["operator"],
        roles=["platform.admin"],
    )

    response = client.get(
        f"/api/v1/users/{OTHER}/audits",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
    )

    assert response.status_code == 200
    assert response.json["total"] == 1


@patch("src.services.user_service.provision_user_identity")
@patch("src.routes.users.SessionLocal")
def test_provision_put_conflict(mock_session, mock_provision, client, rsa_keypair):
    mock_session.return_value.__enter__.return_value = MagicMock()
    mock_provision.side_effect = user_routes.user_service.ConflictError()
    token = _service_token(rsa_keypair)

    response = client.put(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "tenant_uuid": TENANT,
            "idp_id": "user_abc",
            "first_name": "Sam",
            "last_name": "Operator",
            "email": "sam@example.com",
        },
    )

    assert response.status_code == 409
