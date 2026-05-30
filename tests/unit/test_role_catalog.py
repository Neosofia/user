import pytest

from src.domain import role_catalog
from src.domain.role_catalog import (
    assigner_tier1_roles_from_jwt,
    load_catalog_file,
    merge_catalogs,
    platform_role_ids,
    platform_roles_for_tier1,
    platform_roles_for_tier1_roles,
    validate_platform_roles,
    validate_platform_roles_for_assigner,
    validate_platform_roles_for_assigner_tiers,
    validate_tier1_actor,
)

pytestmark = pytest.mark.unit


def test_validate_tier1_actor_accepts_tier1_values():
    validate_tier1_actor("operator")


def test_validate_tier1_actor_rejects_unknown():
    with pytest.raises(ValueError, match="tier1 role"):
        validate_tier1_actor("admin")


def test_assigner_tier1_roles_from_jwt_dedupes_and_filters():
    assert assigner_tier1_roles_from_jwt(["operator", "clinician", "operator"]) == [
        "operator",
        "clinician",
    ]


def test_assigner_tier1_roles_from_jwt_requires_tier1():
    with pytest.raises(ValueError, match="at least one Tier-1 role"):
        assigner_tier1_roles_from_jwt(["admin"])


def test_validate_platform_roles_accepts_v1_subset():
    validate_platform_roles(["operator.platform-admin", "staff.function.member"])


def test_validate_platform_roles_rejects_unknown():
    with pytest.raises(ValueError, match="unknown platform_roles"):
        validate_platform_roles(["clinical.license.rn"])


def test_validate_platform_roles_for_assigner_operator_namespace():
    validate_platform_roles_for_assigner(["operator.audit-reader"], "operator")
    with pytest.raises(ValueError, match="disallowed"):
        validate_platform_roles_for_assigner(["staff.function.member"], "operator")


def test_validate_platform_roles_for_assigner_tiers_union():
    validate_platform_roles_for_assigner_tiers(
        ["operator.audit-reader", "staff.function.member"],
        ["operator", "clinician"],
    )
    with pytest.raises(ValueError, match="disallowed"):
        validate_platform_roles_for_assigner_tiers(
            ["enduser.function.self"],
            ["operator"],
        )


def test_platform_roles_for_tier1_roles_union():
    roles = platform_roles_for_tier1_roles(["operator", "clinician"])
    assert "operator.platform-admin" in roles
    assert "staff.function.member" in roles
    assert "enduser.function.self" not in roles


def test_platform_roles_for_tier1_filters_catalog():
    operator_roles = platform_roles_for_tier1("operator")
    assert "operator.platform-admin" in operator_roles
    assert "staff.function.member" not in operator_roles


def test_default_catalog_includes_operator_platform_admin():
    assert "operator.platform-admin" in platform_role_ids()


def test_catalog_overlay_merges_roles_and_prefixes(tmp_path):
    overlay_path = tmp_path / "roles.json"
    overlay_path.write_text(
        """
        {
          "roles": ["clinical.function.staff-nurse", "research.function.crc"],
          "assigner_prefixes": {"clinician": ["clinical.", "research."]}
        }
        """,
        encoding="utf-8",
    )

    merged = merge_catalogs(role_catalog.role_catalog(), load_catalog_file(overlay_path))

    assert "staff.function.member" in merged.platform_roles
    assert "clinical.function.staff-nurse" in merged.platform_roles
    assert "clinical." in merged.assigner_prefixes["clinician"]


def test_catalog_file_rejects_non_object_json(tmp_path):
    path = tmp_path / "roles.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_catalog_file(path)


def test_catalog_file_rejects_invalid_shapes(tmp_path):
    path = tmp_path / "roles.json"
    path.write_text('{"roles": "operator.platform-admin"}', encoding="utf-8")
    with pytest.raises(ValueError, match="roles list"):
        load_catalog_file(path)

    path.write_text('{"roles": ["bad role"], "assigner_prefixes": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid platform role"):
        load_catalog_file(path)

    path.write_text(
        '{"roles": ["operator.platform-admin"], "assigner_prefixes": []}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="assigner_prefixes"):
        load_catalog_file(path)

    path.write_text(
        '{"roles": ["operator.platform-admin"], "assigner_prefixes": {"operator": "operator."}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be a list"):
        load_catalog_file(path)

    path.write_text(
        '{"roles": ["operator.platform-admin"], "assigner_prefixes": {"operator": ["operator"]}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid assigner prefix"):
        load_catalog_file(path)
