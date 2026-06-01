import pytest

from src.domain import role_catalog
from src.domain.role_catalog import (
    assigner_actors_from_jwt,
    load_catalog_file,
    merge_catalogs,
    role_ids,
    role_short_names,
    roles_for_actor,
    roles_for_actors,
    validate_roles,
    validate_roles_for_assigner_actors,
    validate_actor,
)

pytestmark = pytest.mark.unit


def test_validate_actor_accepts_actor_values():
    validate_actor("operator")


def test_validate_actor_rejects_unknown():
    with pytest.raises(ValueError, match="actor role"):
        validate_actor("admin")


def test_assigner_actors_from_jwt_dedupes_and_filters():
    assert assigner_actors_from_jwt(["operator", "clinician", "operator"]) == [
        "operator",
        "clinician",
    ]


def test_assigner_actors_from_jwt_requires_actor():
    with pytest.raises(ValueError, match="at least one Tier-1 role"):
        assigner_actors_from_jwt(["admin"])


def test_validate_roles_accepts_catalog_slugs():
    validate_roles(["platform.admin", "site.clinical"])


def test_validate_roles_rejects_unknown():
    with pytest.raises(ValueError, match="unknown roles"):
        validate_roles(["clinical.license.rn"])


def test_validate_roles_for_assigner_actors_operator_namespace():
    validate_roles_for_assigner_actors(["platform.audit"], ["operator"])
    with pytest.raises(ValueError, match="disallowed"):
        validate_roles_for_assigner_actors(["site.clinical"], ["operator"])


def test_validate_roles_for_assigner_actors_union():
    validate_roles_for_assigner_actors(
        ["platform.audit", "site.clinical"],
        ["operator", "clinician"],
    )
    with pytest.raises(ValueError, match="disallowed"):
        validate_roles_for_assigner_actors(["patient.self"], ["operator"])


def test_validate_roles_for_assigner_allows_cross_tenant_type_slugs():
    """Platform-tenant users may hold org roles from multiple tenant-type namespaces."""
    roles = [
        "platform.admin",
        "cro.clinical-ops",
        "patient.self",
        "site.clinical",
        "smo.readonly",
    ]
    validate_roles_for_assigner_actors(roles, ["operator", "clinician", "patient"])


def test_roles_for_actors_union():
    roles = roles_for_actors(["operator", "clinician"])
    assert "platform.admin" in roles
    assert "site.clinical" in roles
    assert "patient.self" not in roles


def test_roles_for_actor_filters_catalog():
    operator_roles = roles_for_actor("operator")
    assert "platform.admin" in operator_roles
    assert "site.clinical" not in operator_roles


def test_default_catalog_includes_platform_admin():
    assert "platform.admin" in role_ids()


def test_role_short_names_strips_tenant_prefix():
    assert role_short_names(["platform.admin", "platform.audit"], "platform") == [
        "admin",
        "audit",
    ]


def test_catalog_overlay_merges_roles_and_prefixes(tmp_path):
    overlay_path = tmp_path / "roles.json"
    overlay_path.write_text(
        """
        {
          "tenant_types": {
            "site": { "roles": ["admin", "research", "clinical", "readonly"] }
          },
          "roles": ["site.admin"],
          "assigner_actors": {"clinician": ["site.", "patient."]}
        }
        """,
        encoding="utf-8",
    )

    merged = merge_catalogs(role_catalog.role_catalog(), load_catalog_file(overlay_path))

    assert "site.clinical" in merged.role_ids
    assert "site.admin" in merged.role_ids
    assert "site." in merged.assigner_actors["clinician"]


def test_catalog_file_rejects_non_object_json(tmp_path):
    path = tmp_path / "roles.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_catalog_file(path)


def test_catalog_file_rejects_invalid_shapes(tmp_path):
    path = tmp_path / "roles.json"
    path.write_text('{"roles": "platform.admin"}', encoding="utf-8")
    with pytest.raises(ValueError, match="roles list"):
        load_catalog_file(path)

    path.write_text(
        '{"tenant_types": {}, "roles": ["bad role"], "assigner_actors": {}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid org role"):
        load_catalog_file(path)
