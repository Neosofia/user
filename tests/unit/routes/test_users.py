import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest
from werkzeug.exceptions import NotFound

from src.bootstrap.config import settings
from authorization_in_the_middle.openapi_request import load_openapi_spec, validate_request_body

from src.services import user_service

pytestmark = pytest.mark.unit

TENANT = "00000000-0000-7000-8000-000000000001"
USER = "00000000-0000-7000-8000-000000000002"
OTHER = "00000000-0000-7000-8000-000000000003"
DEFAULT_TENANT_UUID = TENANT

OPERATOR_HEADERS = {"X-Active-Actor": "operator"}
OPENAPI_PATH = Path(__file__).resolve().parents[3] / "openapi.json"


def _claim(name: str) -> str:
    return f"{settings.jwt_claim_namespace}:{name}"


def _token(
    rsa_keypair,
    *,
    sub: str,
    actors: list[str],
    tenant_type: str = "platform",
    tenant_uuid: str = DEFAULT_TENANT_UUID,
    roles: list[str] | None = None,
    session_actors: list[str] | None = None,
):
    claims = {
        "sub": sub,
        "aud": "user",
        "exp": 9999999999,
        "iat": 1,
        _claim("actors"): actors,
        _claim("tenant_type"): tenant_type,
        _claim("tenant_uuid"): tenant_uuid,
    }
    if session_actors is not None:
        claims[_claim("session_actors")] = session_actors
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
        "tos_accepted": False,
    }


@patch("src.services.user_service.get_user_or_404")
def test_list_users_requires_operator(mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["patient"])
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_create_user_with_policy_authorized_actor(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    created = {
        **_sample_user(OTHER),
        "roles": ["patient.self"],
        "display_code": "PAT-9001",
    }
    with patch("src.services.user_service.create_user", return_value=(created, True)) as mock_create:
        token = _token(rsa_keypair, sub=USER, actors=["clinician"])
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
            json={
                "tenant_uuid": TENANT,
                "first_name": "Jordan",
                "last_name": "Lee",
                "email": "jordan@example.com",
                "display_code": "PAT-9001",
                "roles": ["patient.self"],
            },
        )
    assert response.status_code == 201
    assert response.json["display_code"] == "PAT-9001"
    mock_create.assert_called_once()
    planned = mock_create.call_args.args[2]
    assert planned["tenant_uuid"] == TENANT
    assert planned["roles"] == ["patient.self"]


@patch("src.services.user_service.get_user_or_404")
def test_create_user_rejects_patient_actor(mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["patient"])
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "tenant_uuid": TENANT,
            "first_name": "Jordan",
            "last_name": "Lee",
            "email": "jordan@example.com",
            "roles": ["patient.self"],
        },
    )
    assert response.status_code == 403


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_create_user_platform_admin(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    with patch("src.services.user_service.create_user", return_value=(_sample_user(OTHER), True)):
        token = _admin_token(rsa_keypair)
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
            json={
                "tenant_uuid": TENANT,
                "first_name": "Jordan",
                "last_name": "Lee",
                "email": "jordan@example.com",
                "roles": ["platform.admin"],
            },
        )
    assert response.status_code == 201


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_create_user_returns_bad_request_on_value_error(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    mock_session.return_value.__enter__.return_value = MagicMock()
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
        json={
            "tenant_uuid": TENANT,
            "first_name": "Jordan",
            "last_name": "Lee",
            "email": "",
            "roles": ["patient.self"],
        },
    )
    assert response.status_code == 400
    assert "email" in response.json["message"]


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_create_user_returns_conflict(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    mock_session.return_value.__enter__.return_value = MagicMock()
    with patch(
        "src.services.user_service.create_user",
        side_effect=user_service.ConflictError(
            "Display code 'PAT-9001' is already assigned to another user "
            "in this organization."
        ),
    ):
        token = _token(rsa_keypair, sub=USER, actors=["clinician"])
        response = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
            json={
                "tenant_uuid": TENANT,
                "first_name": "Jordan",
                "last_name": "Lee",
                "email": "jordan@example.com",
                "display_code": "PAT-9001",
                "roles": ["patient.self"],
            },
        )
    assert response.status_code == 409
    assert "Display code 'PAT-9001'" in response.json["message"]


@patch("src.services.user_service.get_user_or_404")
def test_create_user_validates_required_fields(mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
        json={
            "tenant_uuid": TENANT,
            "first_name": "Jordan",
            "email": "jordan@example.com",
            "roles": ["patient.self"],
        },
    )
    assert response.status_code == 400
    assert "last_name" in response.json["message"]


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_list_users_clinician_can_list(mock_session, mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    with patch("src.services.user_service.list_users", return_value=([_sample_user()], 1)) as mock_list:
        token = _token(rsa_keypair, sub=USER, actors=["clinician"])
        response = client.get(
            f"/api/v1/tenants/{TENANT}/users",
            headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
        )
    assert response.status_code == 200
    assert response.json["total"] == 1
    assert response.json["tenant_uuid"] == TENANT
    mock_list.assert_called_once()
    assert mock_list.call_args.kwargs["tenant_uuid"] == TENANT


@patch("src.services.user_service.get_user_or_404")
def test_list_tenant_users_denies_other_tenant(mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    other_tenant = "00000000-0000-7000-8000-000000000099"
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.get(
        f"/api/v1/tenants/{other_tenant}/users",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
    )
    assert response.status_code == 403


@patch("src.services.user_service.get_user_or_404")
def test_list_tenant_users_rejects_invalid_tenant_uuid(mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.get(
        "/api/v1/tenants/not-a-uuid/users",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
    )
    # Cedar denies list on a catalog id that does not match principal.tenantId.
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
        token = _admin_token(rsa_keypair, sub=USER)
        response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json["total"] == 1


@patch("src.services.user_service.get_user_or_404")
@patch("src.routes.users.SessionLocal")
def test_list_users_platform_admin_with_mixed_registry_roles(
    mock_session, mock_get_principal, client, rsa_keypair
):
    mixed_row = {
        **_sample_user(),
        "roles": ["site.clinical", "platform.admin", "patient.self"],
    }
    mock_get_principal.return_value = mixed_row
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    with patch("src.services.user_service.list_users", return_value=([_sample_user()], 2)):
        token = _token(
            rsa_keypair,
            sub=USER,
            actors=["operator"],
            tenant_type="platform",
            roles=["admin"],
        )
        response = client.get(
            "/api/v1/users",
            headers={
                "Authorization": f"Bearer {token}",
                **OPERATOR_HEADERS,
            },
        )
    assert response.status_code == 200
    assert response.json["total"] == 2


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
    token = _admin_token(rsa_keypair, sub=USER)
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
    assert "platform.admin" in response.json["roles"]


@patch("src.services.user_service.update_user")
@patch("src.services.user_service.get_user_or_404")
def test_patch_patient_clinician_can_update_profile(mock_load_user, mock_update, client, rsa_keypair):
    clinician = _sample_user(USER)
    clinician["roles"] = ["site.clinical"]
    patient = {
        **_sample_user(OTHER),
        "roles": ["patient.self"],
        "display_code": "PAT-1001",
    }
    updated = {**patient, "first_name": "Alice", "last_name": "Demo"}

    def load_user(user_id: str) -> dict:
        if user_id == USER:
            return clinician
        return patient

    mock_load_user.side_effect = load_user
    mock_update.return_value = updated
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.patch(
        f"/api/v1/users/{OTHER}",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
        json={
            "display_code": "PAT-1001",
            "first_name": "Alice",
            "last_name": "Demo",
            "email": "alice@example.com",
        },
    )
    assert response.status_code == 200
    mock_update.assert_called_once()


@patch("src.services.user_service.get_user_or_404")
def test_patch_patient_clinician_rejects_admin_fields(mock_load_user, client, rsa_keypair):
    clinician = _sample_user(USER)
    patient = {**_sample_user(OTHER), "roles": ["patient.self"]}

    def load_user(user_id: str) -> dict:
        if user_id == USER:
            return clinician
        return patient

    mock_load_user.side_effect = load_user
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    response = client.patch(
        f"/api/v1/users/{OTHER}",
        headers={"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"},
        json={"first_name": "Alice", "roles": ["platform.admin"]},
    )
    assert response.status_code == 403


@patch("src.services.user_service.get_user_or_404")
def test_patch_rejects_cross_prefix_roles_for_platform_user(
    mock_load_user, client, rsa_keypair
):
    target = _sample_user(OTHER)
    mock_load_user.side_effect = lambda user_id: target if user_id == OTHER else _sample_user(user_id)
    tier1 = ["operator", "clinician", "patient"]
    token = _token(
        rsa_keypair,
        sub=USER,
        actors=tier1,
        session_actors=tier1,
        tenant_type="platform",
        roles=["admin"],
    )
    response = client.patch(
        f"/api/v1/users/{OTHER}",
        headers={"Authorization": f"Bearer {token}", **OPERATOR_HEADERS},
        json={
            "roles": [
                "platform.admin",
                "patient.self",
                "site.clinical",
            ],
        },
    )
    assert response.status_code == 403


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
    assert response.status_code == 403


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
    assert "site_uuid" in response.json["message"]


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
    assert response.json["actor_classes"] == ["clinician", "demo", "operator", "patient", "study"]
    assert "platform.admin" in response.json["roles"]
    assert "site.clinical" in response.json["roles"]
    assert any(
        entry["id"] == "platform.admin" and entry["label"]
        for entry in response.json["role_definitions"]
    )


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
    assert "patient.self" in roles


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
    assert "idp_id" in response.json["message"]


def test_openapi_patch_rejects_invalid_tenant_uuid():
    from pathlib import Path

    spec = load_openapi_spec(OPENAPI_PATH)
    schema = spec["components"]["schemas"]["UserUpdateRequest"]
    with pytest.raises(ValueError, match="tenant_uuid"):
        validate_request_body({"tenant_uuid": "not-a-uuid"}, schema, spec)


def test_openapi_patch_rejects_tos_false():
    from pathlib import Path

    spec = load_openapi_spec(OPENAPI_PATH)
    schema = spec["components"]["schemas"]["UserUpdateRequest"]
    with pytest.raises(ValueError, match="tos_accepted"):
        validate_request_body({"tos_accepted": False}, schema, spec)


@patch("src.services.user_service.update_user")
@patch("src.services.user_service.get_user_or_404")
def test_patch_self_accepts_tos(mock_load_user, mock_update, client, rsa_keypair):
    accepted = {**_sample_user(), "tos_accepted": True}
    mock_load_user.return_value = _sample_user()
    mock_update.return_value = accepted
    token = _token(rsa_keypair, sub=USER, actors=["operator"])
    response = client.patch(
        f"/api/v1/users/{USER}",
        headers={"Authorization": f"Bearer {token}"},
        json={"tos_accepted": True},
    )
    assert response.status_code == 200
    assert response.json["tos_accepted"] is True
    mock_update.assert_called_once()


def test_openapi_create_requires_profile_fields():
    from pathlib import Path

    spec = load_openapi_spec(OPENAPI_PATH)
    schema = spec["components"]["schemas"]["UserCreateRequest"]
    with pytest.raises(ValueError):
        validate_request_body({"first_name": "Jordan"}, schema, spec)


def test_openapi_create_requires_tenant_and_roles():
    spec = load_openapi_spec(OPENAPI_PATH)
    schema = spec["components"]["schemas"]["UserCreateRequest"]
    base = {
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
    }
    with pytest.raises(ValueError, match="tenant_uuid"):
        validate_request_body({**base, "roles": ["patient.self"]}, schema, spec)
    with pytest.raises(ValueError, match="roles"):
        validate_request_body({**base, "tenant_uuid": TENANT}, schema, spec)


@patch("src.services.user_service.get_user_or_404")
def test_create_user_rejects_missing_tenant_or_roles(mock_get_principal, client, rsa_keypair):
    mock_get_principal.return_value = _sample_user()
    token = _token(rsa_keypair, sub=USER, actors=["clinician"])
    headers = {"Authorization": f"Bearer {token}", "X-Active-Actor": "clinician"}
    base = {
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
    }
    missing_tenant = client.post(
        "/api/v1/users",
        headers=headers,
        json={**base, "roles": ["patient.self"]},
    )
    assert missing_tenant.status_code == 400
    assert "tenant_uuid" in missing_tenant.json["message"]

    missing_roles = client.post(
        "/api/v1/users",
        headers=headers,
        json={**base, "tenant_uuid": TENANT},
    )
    assert missing_roles.status_code == 400
    assert "roles" in missing_roles.json["message"]


def test_finalize_create_body_normalizes_fields():
    planned = user_service.finalize_create_body(
        {
            "first_name": "Jordan",
            "last_name": "Lee",
            "email": "jordan@example.com",
            "tenant_uuid": TENANT,
            "roles": ["platform.admin"],
        },
    )
    assert planned["tenant_uuid"] == TENANT
    assert planned["roles"] == ["platform.admin"]


def test_finalize_create_body_requires_tenant():
    with pytest.raises(ValueError, match="tenant_uuid is required"):
        user_service.finalize_create_body(
            {
                "first_name": "Jordan",
                "last_name": "Lee",
                "email": "jordan@example.com",
                "roles": ["platform.admin"],
            },
        )


def test_openapi_provision_rejects_invalid_fields():
    from pathlib import Path

    spec = load_openapi_spec(OPENAPI_PATH)
    schema = spec["components"]["schemas"]["UserProvisionRequest"]
    valid = {
        "tenant_uuid": TENANT,
        "idp_id": "user_abc",
        "first_name": "Sam",
        "last_name": "Operator",
        "email": "sam@example.com",
    }
    with pytest.raises(ValueError, match="tenant_uuid"):
        validate_request_body({**valid, "tenant_uuid": "not-a-uuid"}, schema, spec)
    with pytest.raises(ValueError, match="idp_id"):
        validate_request_body({**valid, "idp_id": ""}, schema, spec)
    with pytest.raises(ValueError, match="roles"):
        validate_request_body({**valid, "roles": ["operator"]}, schema, spec)


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
    principal = _sample_user(USER)
    target = _sample_user(OTHER)

    def load_user(user_id: str) -> dict:
        if user_id == USER:
            return principal
        return target

    mock_get_user.side_effect = load_user
    mock_session.return_value.__enter__.return_value = MagicMock()
    mock_get_audits.return_value = ([], 0)
    token = _token(
        rsa_keypair,
        sub=USER,
        actors=["operator"],
        roles=["admin"],
    )

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
    token = _admin_token(rsa_keypair, sub=USER)

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
    mock_provision.side_effect = user_service.ConflictError()
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
