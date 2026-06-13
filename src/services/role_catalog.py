"""Load and validate ``roles/default.json`` (+ optional deploy overlay). Vocabulary only — not authz."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.bootstrap.config import settings

DEFAULT_ROLE_CATALOG_PATH = Path(__file__).resolve().parents[2] / "roles" / "default.json"

# Registry slugs under ``patient.*``; not an org ``tenant_types`` key.
PATIENT_ROLE_NAMESPACE = "patient"


@dataclass(frozen=True)
class RoleCatalog:
    role_ids: frozenset[str]
    tenant_types: dict[str, frozenset[str]]
    role_labels: dict[str, str]


def _default_role_label(role_id: str) -> str:
    _, _, short = role_id.partition(".")
    return short.replace("-", " ").title()


def _role_id(value: object, allowed_namespaces: frozenset[str]) -> str:
    if isinstance(value, str):
        role_id = value.strip()
    elif isinstance(value, dict):
        role_id = str(value.get("id", "")).strip()
    else:
        role_id = ""
    if not role_id or any(char.isspace() for char in role_id) or "." not in role_id:
        raise ValueError(f"invalid org role id: {value!r}")
    namespace, _, short = role_id.partition(".")
    if short and namespace in allowed_namespaces:
        return role_id
    raise ValueError(f"invalid org role id: {value!r}")


def _tenant_types_from_mapping(data: dict[str, Any], source: Path) -> dict[str, frozenset[str]]:
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
            short = str(raw_role).strip()
            if not short:
                raise ValueError(f"invalid org role for {key}: {raw_role!r}")
            roles.append(short)
        tenant_types[key] = frozenset(roles)
    return tenant_types


def _role_entry(
    role: object,
    source: Path,
    allowed_namespaces: frozenset[str],
) -> tuple[str, str]:
    if isinstance(role, str):
        role_id = _role_id(role, allowed_namespaces)
        return role_id, _default_role_label(role_id)
    if isinstance(role, dict):
        role_id = _role_id(role, allowed_namespaces)
        raw_label = role.get("label")
        label = str(raw_label).strip() if raw_label is not None else ""
        return role_id, label or _default_role_label(role_id)
    raise ValueError(f"{source} roles entries must be strings or objects with id")


def _allowed_namespaces(tenant_types: dict[str, frozenset[str]]) -> frozenset[str]:
    return frozenset(tenant_types.keys()) | frozenset({PATIENT_ROLE_NAMESPACE})


def _catalog_from_mapping(data: dict[str, Any], source: Path) -> RoleCatalog:
    tenant_types = _tenant_types_from_mapping(data, source)
    allowed_namespaces = _allowed_namespaces(tenant_types)

    raw_roles = data.get("roles")
    if not isinstance(raw_roles, list):
        raise ValueError(f"{source} must contain a roles list")
    role_labels: dict[str, str] = {}
    for role in raw_roles:
        role_id, label = _role_entry(role, source, allowed_namespaces)
        role_labels[role_id] = label
    roles = frozenset(role_labels)

    return RoleCatalog(
        role_ids=roles,
        tenant_types=tenant_types,
        role_labels=role_labels,
    )


def load_catalog_file(path: Path) -> RoleCatalog:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    return _catalog_from_mapping(data, path)


def merge_catalogs(default: RoleCatalog, overlay: RoleCatalog | None) -> RoleCatalog:
    if overlay is None:
        return default
    tenant_types = dict(default.tenant_types)
    for tenant_type, roles in overlay.tenant_types.items():
        tenant_types[tenant_type] = roles | tenant_types.get(tenant_type, frozenset())
    role_labels = dict(default.role_labels)
    role_labels.update(overlay.role_labels)
    return RoleCatalog(
        role_ids=frozenset(default.role_ids | overlay.role_ids),
        tenant_types=tenant_types,
        role_labels=role_labels,
    )


@lru_cache(maxsize=1)
def role_catalog() -> RoleCatalog:
    default = load_catalog_file(DEFAULT_ROLE_CATALOG_PATH)
    overlay_path = settings.role_catalog_overlay
    overlay = load_catalog_file(overlay_path) if overlay_path else None
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
