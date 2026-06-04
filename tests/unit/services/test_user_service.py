import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound

from src.models.user import User
from src.services import user_service

pytestmark = pytest.mark.unit

TENANT = uuid.UUID("00000000-0000-7000-8000-000000000001")
USER_ID = uuid.UUID("00000000-0000-7000-8000-000000000002")
OTHER_USER_ID = uuid.UUID("00000000-0000-7000-8000-000000000003")


def _user_row(**overrides) -> User:
    row = User(
        uuid=USER_ID,
        tenant_uuid=TENANT,
        idp_id="user_abc",
        first_name="Sam",
        last_name="Operator",
        email="sam@example.com",
        roles=["platform.admin"],
        change_type=1,
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def test_get_user_or_404_invalid_uuid():
    with pytest.raises(NotFound):
        user_service.get_user_or_404("not-a-uuid")


@patch("src.db.engine.SessionLocal")
def test_get_user_or_404_missing_row(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db
    mock_db.get.return_value = None

    with pytest.raises(NotFound):
        user_service.get_user_or_404(str(USER_ID))


@patch("src.db.engine.SessionLocal")
def test_get_user_or_404_returns_dict(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db
    row = _user_row()
    mock_db.get.return_value = row

    result = user_service.get_user_or_404(str(USER_ID))

    assert result["uuid"] == str(USER_ID)
    assert result["roles"] == ["platform.admin"]


def test_list_users_without_search():
    mock_db = MagicMock()
    row = _user_row()
    mock_db.scalar.return_value = 1
    mock_db.scalars.return_value.all.return_value = [row]

    items, total = user_service.list_users(mock_db, page=1, page_size=10, search="")

    assert total == 1
    assert items[0]["email"] == "sam@example.com"
    mock_db.scalar.assert_called_once()


def test_list_users_with_search():
    mock_db = MagicMock()
    mock_db.scalar.return_value = 0
    mock_db.scalars.return_value.all.return_value = []

    items, total = user_service.list_users(mock_db, page=2, page_size=5, search="sam")

    assert items == []
    assert total == 0


def test_update_user_self_service_fields():
    mock_db = MagicMock()
    row = _user_row()
    mock_db.get.return_value = row

    result = user_service.update_user(
        mock_db,
        str(USER_ID),
        str(USER_ID),
        {"first_name": "  Ben  ", "last_name": "", "email": None},
        self_service=True,
    )

    assert row.first_name == "Ben"
    assert row.last_name is None
    assert row.email is None
    assert row.changed_by_uuid == USER_ID
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(row)
    assert result["first_name"] == "Ben"


def test_update_user_self_service_accepts_tos():
    mock_db = MagicMock()
    row = _user_row(tos_accepted=False)
    mock_db.get.return_value = row

    result = user_service.update_user(
        mock_db,
        str(USER_ID),
        str(USER_ID),
        {"tos_accepted": True},
        self_service=True,
    )

    assert row.tos_accepted is True
    assert result["tos_accepted"] is True


def test_update_user_operator_fields():
    mock_db = MagicMock()
    row = _user_row()
    mock_db.get.return_value = row
    new_tenant = uuid.UUID("00000000-0000-7000-8000-000000000099")

    user_service.update_user(
        mock_db,
        str(USER_ID),
        str(USER_ID),
        {
            "tenant_uuid": str(new_tenant),
            "roles": ["site.clinical"],
        },
        self_service=False,
    )

    assert row.tenant_uuid == new_tenant
    assert row.roles == ["site.clinical"]


def _provision_payload(**overrides) -> dict:
    payload = {
        "tenant_uuid": str(TENANT),
        "idp_id": "user_abc",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
    }
    payload.update(overrides)
    return payload


def test_provision_user_identity_inserts_with_empty_roles():
    mock_db = MagicMock()
    mock_db.get.return_value = None
    mock_db.scalar.return_value = 0

    result, created = user_service.provision_user_identity(
        mock_db,
        str(USER_ID),
        _provision_payload(actors=["clinician"]),
    )

    row = mock_db.add.call_args.args[0]
    assert created is True
    assert row.uuid == USER_ID
    assert row.roles == []
    assert row.changed_by_type == user_service.SERVICE_ACTOR_TYPE
    assert result["email"] == "ada@example.com"


def test_provision_user_identity_bootstraps_first_operator():
    mock_db = MagicMock()
    mock_db.get.return_value = None
    mock_db.scalar.return_value = 0

    result, created = user_service.provision_user_identity(
        mock_db,
        str(USER_ID),
        _provision_payload(actors=["operator", "clinician"]),
    )

    row = mock_db.add.call_args.args[0]
    assert created is True
    assert row.roles == ["platform.admin"]
    assert result["roles"] == ["platform.admin"]


def test_provision_user_identity_skips_bootstrap_when_platform_admin_exists():
    mock_db = MagicMock()
    mock_db.get.return_value = None
    mock_db.scalar.return_value = 1

    _, created = user_service.provision_user_identity(
        mock_db,
        str(USER_ID),
        _provision_payload(actors=["operator"]),
    )

    row = mock_db.add.call_args.args[0]
    assert created is True
    assert row.roles == []


def test_provision_user_identity_creates_row_when_user_absent():
    mock_db = MagicMock()
    mock_db.get.return_value = None
    mock_db.scalar.return_value = 0

    result, created = user_service.provision_user_identity(
        mock_db,
        str(USER_ID),
        _provision_payload(actors=["operator"]),
    )

    row = mock_db.add.call_args.args[0]
    assert created is True
    assert row.roles == ["platform.admin"]
    assert result["roles"] == ["platform.admin"]


def test_provision_user_identity_updates_identity_only():
    mock_db = MagicMock()
    row = _user_row(roles=["platform.admin"])
    mock_db.get.return_value = row

    result, created = user_service.provision_user_identity(
        mock_db,
        str(USER_ID),
        _provision_payload(first_name=" Grace ", email="grace@example.com"),
    )

    assert created is False
    assert row.first_name == "Grace"
    assert row.email == "grace@example.com"
    assert row.roles == ["platform.admin"]
    assert result["roles"] == ["platform.admin"]


@patch("src.domain.role_catalog.merge_provision_default_roles")
def test_provision_user_identity_backfills_default_roles_on_login(merge_defaults):
    merge_defaults.return_value = ["site.clinical", "patient.self"]
    mock_db = MagicMock()
    row = _user_row(roles=[])
    mock_db.get.return_value = row
    mock_db.scalar.return_value = 1

    result, created = user_service.provision_user_identity(
        mock_db,
        str(USER_ID),
        _provision_payload(actors=["clinician", "patient"]),
    )

    assert created is False
    assert row.roles == ["site.clinical", "patient.self"]
    assert result["roles"] == ["site.clinical", "patient.self"]
    merge_defaults.assert_called_once_with(
        ["clinician", "patient"],
        [],
    )


def test_provision_user_identity_integrity_conflict():
    mock_db = MagicMock()
    row = _user_row()
    mock_db.get.return_value = row
    mock_db.commit.side_effect = IntegrityError("stmt", {}, Exception("dup"))

    with pytest.raises(user_service.ConflictError):
        user_service.provision_user_identity(mock_db, str(USER_ID), _provision_payload())

    mock_db.rollback.assert_called_once()


def test_update_user_not_found():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    with pytest.raises(NotFound):
        user_service.update_user(
            mock_db,
            str(USER_ID),
            str(USER_ID),
            {"first_name": "X"},
            self_service=True,
        )


def test_update_user_integrity_conflict():
    mock_db = MagicMock()
    row = _user_row()
    mock_db.get.return_value = row
    mock_db.commit.side_effect = IntegrityError("stmt", {}, Exception("dup"))

    with pytest.raises(user_service.ConflictError):
        user_service.update_user(
            mock_db,
            str(USER_ID),
            str(USER_ID),
            {"email": "dup@example.com"},
            self_service=True,
        )

    mock_db.rollback.assert_called_once()


def test_get_user_audits_user_missing():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    with pytest.raises(NotFound):
        user_service.get_user_audits(mock_db, str(USER_ID), page=1, page_size=10)


def test_get_user_audits_returns_items():
    mock_db = MagicMock()
    mock_db.get.return_value = _user_row()
    mock_db.scalar.return_value = 1
    changed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mock_db.execute.return_value.mappings.return_value.all.return_value = [
        {
            "history_uuid": uuid.uuid4(),
            "uuid": USER_ID,
            "tenant_uuid": TENANT,
            "idp_id": "user_abc",
            "display_code": "DET-4035",
            "first_name": "Sam",
            "last_name": "Operator",
            "email": "sam@example.com",
            "roles": ["platform.admin"],
            "changed_at": changed_at,
            "changed_by_uuid": USER_ID,
            "changed_by_type": 1,
            "change_type": 2,
        }
    ]

    items, total = user_service.get_user_audits(mock_db, str(USER_ID), page=1, page_size=10)

    assert total == 1
    assert items[0]["changed_at"] == changed_at.isoformat()
    assert items[0]["change_type"] == 2


def test_create_user_defaults_patient_role_for_clinician():
    mock_db = MagicMock()
    mock_db.get.return_value = None
    mock_db.scalar.return_value = None
    payload = {
        "tenant_uuid": str(TENANT),
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
        "display_code": "PAT-9001",
    }

    result, created = user_service.create_user(
        mock_db,
        str(USER_ID),
        payload,
        assigner_actor_list=["clinician"],
    )

    assert created is True
    assert result["roles"] == ["patient.self"]
    assert result["display_code"] == "PAT-9001"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_create_user_rejects_non_patient_roles_for_clinician():
    mock_db = MagicMock()
    payload = {
        "tenant_uuid": str(TENANT),
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
        "roles": ["site.clinical"],
    }

    with pytest.raises(ValueError, match="patient.self"):
        user_service.create_user(
            mock_db,
            str(USER_ID),
            payload,
            assigner_actor_list=["clinician"],
        )


def test_create_user_clinician_enrollment_skips_assigner_catalog():
    mock_db = MagicMock()
    mock_db.get.return_value = None
    mock_db.scalar.return_value = None
    payload = {
        "tenant_uuid": str(TENANT),
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
        "roles": ["patient.self"],
    }

    result, created = user_service.create_user(
        mock_db,
        str(USER_ID),
        payload,
        assigner_actor_list=["clinician"],
    )

    assert created is True
    assert result["roles"] == ["patient.self"]


def test_create_user_upserts_when_uuid_provided():
    mock_db = MagicMock()
    existing = MagicMock()
    mock_db.get.return_value = existing
    mock_db.scalar.return_value = None
    payload = {
        "tenant_uuid": str(TENANT),
        "uuid": str(OTHER_USER_ID),
        "idp_id": "demo_patient_pat_9001",
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
        "display_code": "PAT-9001",
        "roles": ["patient.self"],
    }

    with patch.object(user_service, "_row_to_dict", return_value={"uuid": str(OTHER_USER_ID)}):
        result, created = user_service.create_user(
            mock_db,
            str(USER_ID),
            payload,
            assigner_actor_list=["operator"],
        )

    assert created is False
    assert result["uuid"] == str(OTHER_USER_ID)
    mock_db.add.assert_not_called()
    mock_db.commit.assert_called_once()


def test_create_user_rejects_duplicate_display_code():
    mock_db = MagicMock()
    mock_db.get.return_value = None
    mock_db.scalar.return_value = uuid.uuid4()
    payload = {
        "tenant_uuid": str(TENANT),
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
        "display_code": "PAT-9001",
    }

    with pytest.raises(user_service.ConflictError, match="Display code 'PAT-9001'"):
        user_service.create_user(
            mock_db,
            str(USER_ID),
            payload,
            assigner_actor_list=["clinician"],
        )

    mock_db.commit.assert_not_called()


def test_create_user_rejects_uuid_for_clinician():
    mock_db = MagicMock()
    payload = {
        "tenant_uuid": str(TENANT),
        "uuid": str(OTHER_USER_ID),
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
        "roles": ["patient.self"],
    }

    with pytest.raises(ValueError, match="uuid or idp_id"):
        user_service.create_user(
            mock_db,
            str(USER_ID),
            payload,
            assigner_actor_list=["clinician"],
        )


def test_create_user_rejects_non_patient_roles_for_stable_uuid_seeding():
    mock_db = MagicMock()
    payload = {
        "tenant_uuid": str(TENANT),
        "uuid": str(OTHER_USER_ID),
        "first_name": "Jordan",
        "last_name": "Lee",
        "email": "jordan@example.com",
        "roles": ["site.clinical"],
    }

    with pytest.raises(ValueError, match="stable uuid seeding"):
        user_service.create_user(
            mock_db,
            str(USER_ID),
            payload,
            assigner_actor_list=["operator"],
        )
