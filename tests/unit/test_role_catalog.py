import pytest

from src.services.role_catalog import (
    load_catalog_file,
    merge_catalogs,
    role_ids,
    tenant_type_roles,
    validate_roles,
)

pytestmark = pytest.mark.unit


def test_validate_roles_accepts_catalog_slugs():
    validate_roles(["platform.admin", "site.clinical"])


def test_validate_roles_rejects_unknown():
    with pytest.raises(ValueError, match="unknown roles"):
        validate_roles(["clinical.license.rn"])


def test_merged_catalog_includes_product_roles():
    assert "platform.admin" in role_ids()


def test_merged_catalog_assigns_demo_roles_on_platform():
    platform_roles = tenant_type_roles()["platform"]
    assert "patient.self" in platform_roles
    assert "site.clinical" in platform_roles


def test_catalog_role_objects_with_labels(tmp_path):
    path = tmp_path / "roles.json"
    path.write_text(
        """
        {
          "tenant_types": {
            "site": { "roles": ["site.clinical", "patient.self"] }
          },
          "roles": [
            "site.clinical",
            { "id": "patient.self", "label": "Patient" }
          ]
        }
        """,
        encoding="utf-8",
    )
    catalog = load_catalog_file(path)
    assert catalog.role_labels["patient.self"] == "Patient"


def test_role_definition_falls_back_to_slug_label(tmp_path):
    from src.services.role_catalog import _default_role_label, role_definition

    path = tmp_path / "roles.json"
    path.write_text('{"tenant_types": {}, "roles": ["site.clinical"]}', encoding="utf-8")
    base = load_catalog_file(path)
    assert base.role_labels["site.clinical"] == _default_role_label("site.clinical")
    assert base.role_labels["site.clinical"] == "Clinical"

    entry = role_definition("platform.admin")
    assert entry["id"] == "platform.admin"
    assert entry["label"] == "Platform Admin"


def test_catalog_overlay_merges_roles(tmp_path):
    base_path = tmp_path / "base.json"
    base_path.write_text('{"tenant_types": {}, "roles": []}', encoding="utf-8")
    overlay_path = tmp_path / "overlay.json"
    overlay_path.write_text(
        """
        {
          "tenant_types": {
            "site": {
              "roles": ["site.admin", "site.research", "site.clinical", "site.readonly"]
            }
          },
          "roles": ["site.admin", "site.research", "site.clinical", "site.readonly"]
        }
        """,
        encoding="utf-8",
    )

    merged = merge_catalogs(
        load_catalog_file(base_path),
        load_catalog_file(overlay_path, validate_assignable_refs=False),
    )

    assert "site.clinical" in merged.role_ids
    assert "site.admin" in merged.role_ids


def test_catalog_file_rejects_non_object_json(tmp_path):
    path = tmp_path / "roles.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_catalog_file(path)


def test_catalog_file_rejects_invalid_shapes(tmp_path):
    path = tmp_path / "roles.json"
    path.write_text(
        '{"tenant_types": {"platform": {"roles": ["platform.admin"]}}, "roles": "platform.admin"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="roles list"):
        load_catalog_file(path)

    path.write_text('{"tenant_types": {}, "roles": ["bad role"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid role slug"):
        load_catalog_file(path)


def test_catalog_rejects_unknown_assignable_slug(tmp_path):
    path = tmp_path / "roles.json"
    path.write_text(
        """
        {
          "tenant_types": { "site": { "roles": ["site.missing"] } },
          "roles": ["site.clinical"]
        }
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="tenant_types reference unknown roles"):
        load_catalog_file(path)
