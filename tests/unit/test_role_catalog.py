import pytest

from src.domain.role_catalog import (
    V1_PLATFORM_ROLES,
    assigner_tier1_roles_from_jwt,
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
    validate_platform_roles(["operator.platform-admin", "clinical.function.surgeon"])


def test_validate_platform_roles_rejects_unknown():
    with pytest.raises(ValueError, match="unknown platform_roles"):
        validate_platform_roles(["clinical.license.rn"])


def test_validate_platform_roles_for_assigner_operator_namespace():
    validate_platform_roles_for_assigner(["operator.audit-reader"], "operator")
    with pytest.raises(ValueError, match="disallowed"):
        validate_platform_roles_for_assigner(["clinical.function.staff-nurse"], "operator")


def test_validate_platform_roles_for_assigner_tiers_union():
    validate_platform_roles_for_assigner_tiers(
        ["operator.audit-reader", "clinical.function.staff-nurse"],
        ["operator", "clinician"],
    )
    with pytest.raises(ValueError, match="disallowed"):
        validate_platform_roles_for_assigner_tiers(
            ["patient.function.self"],
            ["operator"],
        )


def test_platform_roles_for_tier1_roles_union():
    roles = platform_roles_for_tier1_roles(["operator", "clinician"])
    assert "operator.platform-admin" in roles
    assert "clinical.function.staff-nurse" in roles
    assert "patient.function.self" not in roles


def test_platform_roles_for_tier1_filters_catalog():
    operator_roles = platform_roles_for_tier1("operator")
    assert "operator.platform-admin" in operator_roles
    assert "clinical.function.staff-nurse" not in operator_roles


def test_v1_catalog_includes_operator_platform_admin():
    assert "operator.platform-admin" in V1_PLATFORM_ROLES
