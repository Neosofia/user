"""Load optional base role catalog and merge deploy overlay. Vocabulary only — not authz."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.bootstrap.config import settings

DEFAULT_ROLE_CATALOG_PATH = Path(__file__).resolve().parents[2] / "policies" / "roles" / "default.json"


@dataclass(frozen=True)
class RoleCatalog:
    role_ids: frozenset[str]
    tenant_types: dict[str, frozenset[str]]
    role_labels: dict[str, str]


def _empty_role_catalog() -> RoleCatalog:
    return RoleCatalog(role_ids=frozenset(), tenant_types={}, role_labels={})


def _load_default_catalog() -> RoleCatalog:
    if not DEFAULT_ROLE_CATALOG_PATH.is_file():
        return _empty_role_catalog()
    return load_catalog_file(DEFAULT_ROLE_CATALOG_PATH)


def _default_role_label(role_id: str) -> str:
    _, _, short = role_id.partition(".")
    return short.replace("-", " ").title()


def _role_slug(value: object) -> str:
    if isinstance(value, str):
        role_id = value.strip()
    elif isinstance(value, dict):
        role_id = str(value.get("id", "")).strip()
    else:
        role_id = ""
    namespace, _, short = role_id.partition(".")
    if not role_id or any(char.isspace() for char in role_id) or not namespace or not short:
        raise ValueError(f"invalid role slug: {value!r}")
    return role_id


def _role_labels_from_list(raw_roles: list[object], source: Path) -> dict[str, str]:
    role_labels: dict[str, str] = {}
    for role in raw_roles:
        if isinstance(role, str):
            role_id = _role_slug(role)
            role_labels[role_id] = _default_role_label(role_id)
            continue
        if isinstance(role, dict):
            role_id = _role_slug(role)
            raw_label = role.get("label")
            label = str(raw_label).strip() if raw_label is not None else ""
            role_labels[role_id] = label or _default_role_label(role_id)
            continue
        raise ValueError(f"{source} roles entries must be strings or objects with id")
    return role_labels


def _assert_assignable_refs_known(
    tenant_types: dict[str, frozenset[str]],
    role_ids: frozenset[str],
    source: str | Path,
) -> None:
    unknown = sorted({slug for slugs in tenant_types.values() for slug in slugs} - role_ids)
    if unknown:
        raise ValueError(f"{source} tenant_types reference unknown roles: {unknown}")


def _assignable_roles_by_tenant_type(
    data: dict[str, Any],
    source: Path,
) -> dict[str, frozenset[str]]:
    raw = data.get("tenant_types")
    if not isinstance(raw, dict):
        raise ValueError(f"{source} must contain tenant_types object")
    tenant_types: dict[str, frozenset[str]] = {}
    for tenant_type, entry in raw.items():
        key = str(tenant_type).strip()
        if not key:
            raise ValueError(f"invalid tenant type in {source}: {tenant_type!r}")
        if not isinstance(entry, dict):
            raise ValueError(f"tenant_types.{key} must be an object")
        raw_roles = entry.get("roles")
        if not isinstance(raw_roles, list):
            raise ValueError(f"tenant_types.{key}.roles must be a list")
        roles: list[str] = []
        for raw_role in raw_roles:
            slug = _role_slug(raw_role)
            roles.append(slug)
        tenant_types[key] = frozenset(roles)

    return tenant_types


def _catalog_from_mapping(
    data: dict[str, Any],
    source: Path,
    *,
    validate_assignable_refs: bool = True,
) -> RoleCatalog:
    raw_roles = data.get("roles")
    if not isinstance(raw_roles, list):
        raise ValueError(f"{source} must contain a roles list")
    role_labels = _role_labels_from_list(raw_roles, source)
    role_ids_set = frozenset(role_labels)
    tenant_types = _assignable_roles_by_tenant_type(data, source)
    if validate_assignable_refs:
        _assert_assignable_refs_known(tenant_types, role_ids_set, source)

    return RoleCatalog(
        role_ids=role_ids_set,
        tenant_types=tenant_types,
        role_labels=role_labels,
    )


def load_catalog_file(path: Path, *, validate_assignable_refs: bool = True) -> RoleCatalog:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    return _catalog_from_mapping(data, path, validate_assignable_refs=validate_assignable_refs)


def merge_catalogs(default: RoleCatalog, overlay: RoleCatalog | None) -> RoleCatalog:
    if overlay is None:
        return default
    tenant_types = dict(default.tenant_types)
    for tenant_type, roles in overlay.tenant_types.items():
        tenant_types[tenant_type] = roles | tenant_types.get(tenant_type, frozenset())
    role_labels = dict(default.role_labels)
    role_labels.update(overlay.role_labels)
    merged = RoleCatalog(
        role_ids=frozenset(default.role_ids | overlay.role_ids),
        tenant_types=tenant_types,
        role_labels=role_labels,
    )
    _assert_assignable_refs_known(merged.tenant_types, merged.role_ids, "merged role catalog")
    return merged


@lru_cache(maxsize=1)
def role_catalog() -> RoleCatalog:
    default = _load_default_catalog()
    overlay_path = settings.role_catalog_overlay
    overlay = (
        load_catalog_file(overlay_path, validate_assignable_refs=False)
        if overlay_path
        else None
    )
    return merge_catalogs(default, overlay)


def role_ids() -> frozenset[str]:
    return role_catalog().role_ids


def tenant_type_roles() -> dict[str, frozenset[str]]:
    return role_catalog().tenant_types


def role_labels() -> dict[str, str]:
    return role_catalog().role_labels


def role_definition(role_id: str) -> dict[str, str]:
    labels = role_labels()
    return {"id": role_id, "label": labels.get(role_id, _default_role_label(role_id))}


def validate_roles(roles: list[str]) -> None:
    unknown = sorted(set(roles) - role_ids())
    if unknown:
        raise ValueError(f"unknown roles: {unknown}")
