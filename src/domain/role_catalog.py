"""File-backed org role catalog with optional deploy-time overlay (ADR-0014)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.bootstrap.config import settings

DEFAULT_ROLE_CATALOG_PATH = Path(__file__).resolve().parents[2] / "roles" / "default.json"

_tier1_actor_classes: frozenset[str] = frozenset()


def init_actor_classes(classes: frozenset[str]) -> None:
    """Set Tier-1 actors from Flask startup (platform-actors.json or test config)."""
    global _tier1_actor_classes
    _tier1_actor_classes = classes


def actor_classes() -> frozenset[str]:
    """Tier-1 actors from Authentication platform-actors.json (cached on the Flask app)."""
    from flask import has_app_context, current_app

    from authentication_in_the_middle.actors import ensure_tier1_actor_classes

    if has_app_context():
        return ensure_tier1_actor_classes(current_app)
    return _tier1_actor_classes


VALID_TENANT_TYPES: frozenset[str] = frozenset(
    {"platform", "cro", "sponsor", "site", "smo", "patient"}
)


@dataclass(frozen=True)
class RoleCatalog:
    role_ids: frozenset[str]
    tenant_types: dict[str, frozenset[str]]
    assigner_actors: dict[str, tuple[str, ...]]
    role_labels: dict[str, str]


def _default_role_label(role_id: str) -> str:
    _, _, short = role_id.partition(".")
    return short.replace("-", " ").title()


def _role_id(value: object) -> str:
    if isinstance(value, str):
        role_id = value.strip()
    elif isinstance(value, dict):
        role_id = str(value.get("id", "")).strip()
    else:
        role_id = ""
    if not role_id or any(char.isspace() for char in role_id) or "." not in role_id:
        raise ValueError(f"invalid org role id: {value!r}")
    tenant_type, _, org_role = role_id.partition(".")
    if tenant_type not in VALID_TENANT_TYPES or not org_role:
        raise ValueError(f"invalid org role id: {value!r}")
    return role_id


def _prefixes(value: object, actor: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"assigner_actors.{actor} must be a list")
    prefixes: list[str] = []
    seen: set[str] = set()
    for raw in value:
        prefix = str(raw).strip()
        if not prefix or any(char.isspace() for char in prefix) or not prefix.endswith("."):
            raise ValueError(f"invalid assigner prefix for {actor}: {raw!r}")
        tenant_type = prefix[:-1]
        if tenant_type not in VALID_TENANT_TYPES:
            raise ValueError(f"invalid assigner prefix for {actor}: {raw!r}")
        if prefix not in seen:
            seen.add(prefix)
            prefixes.append(prefix)
    return tuple(prefixes)


def _tenant_types_from_mapping(data: dict[str, Any], source: Path) -> dict[str, frozenset[str]]:
    raw = data.get("tenant_types")
    if not isinstance(raw, dict):
        raise ValueError(f"{source} must contain tenant_types object")
    tenant_types: dict[str, frozenset[str]] = {}
    for tenant_type, entry in raw.items():
        key = str(tenant_type).strip()
        if key not in VALID_TENANT_TYPES:
            raise ValueError(f"unknown tenant type in {source}: {tenant_type!r}")
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
            _role_id(f"{key}.{short}")
            roles.append(short)
        tenant_types[key] = frozenset(roles)
    return tenant_types


def _role_entry(role: object, source: Path) -> tuple[str, str]:
    if isinstance(role, str):
        role_id = _role_id(role)
        return role_id, _default_role_label(role_id)
    if isinstance(role, dict):
        role_id = _role_id(role)
        raw_label = role.get("label")
        label = str(raw_label).strip() if raw_label is not None else ""
        return role_id, label or _default_role_label(role_id)
    raise ValueError(f"{source} roles entries must be strings or objects with id")


def _catalog_from_mapping(data: dict[str, Any], source: Path) -> RoleCatalog:
    raw_roles = data.get("roles")
    if not isinstance(raw_roles, list):
        raise ValueError(f"{source} must contain a roles list")
    role_labels: dict[str, str] = {}
    for role in raw_roles:
        role_id, label = _role_entry(role, source)
        role_labels[role_id] = label
    roles = frozenset(role_labels)
    tenant_types = _tenant_types_from_mapping(data, source)

    raw_prefixes = data.get("assigner_actors", {})
    if not isinstance(raw_prefixes, dict):
        raise ValueError(f"{source} assigner_actors must be an object")
    prefixes: dict[str, tuple[str, ...]] = {}
    for actor, raw_value in raw_prefixes.items():
        actor_key = str(actor).strip()
        validate_actor(actor_key)
        prefixes[actor_key] = _prefixes(raw_value, actor_key)
    return RoleCatalog(
        role_ids=roles,
        tenant_types=tenant_types,
        assigner_actors=prefixes,
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
    prefixes: dict[str, list[str]] = {
        actor: list(values) for actor, values in default.assigner_actors.items()
    }
    for actor, values in overlay.assigner_actors.items():
        existing = prefixes.setdefault(actor, [])
        for prefix in values:
            if prefix not in existing:
                existing.append(prefix)
    role_labels = dict(default.role_labels)
    role_labels.update(overlay.role_labels)
    return RoleCatalog(
        role_ids=frozenset(default.role_ids | overlay.role_ids),
        tenant_types=tenant_types,
        assigner_actors={actor: tuple(values) for actor, values in prefixes.items()},
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


def assigner_actors() -> dict[str, tuple[str, ...]]:
    return role_catalog().assigner_actors


def role_labels() -> dict[str, str]:
    return role_catalog().role_labels


def role_definition(role_id: str) -> dict[str, str]:
    labels = role_labels()
    return {"id": role_id, "label": labels.get(role_id, _default_role_label(role_id))}


def roles_for_actor(actor: str) -> frozenset[str]:
    prefixes = assigner_actors().get(actor, ())
    return frozenset(
        role for role in role_ids() if any(role.startswith(prefix) for prefix in prefixes)
    )


def assigner_actors_from_jwt(roles: list[str]) -> list[str]:
    """Distinct Tier-1 roles from JWT, preserving claim order."""
    actor: list[str] = []
    seen: set[str] = set()
    for role in roles:
        if role in actor_classes() and role not in seen:
            seen.add(role)
            actor.append(role)
    if not actor:
        raise ValueError(
            "JWT must include at least one Tier-1 role (operator, study, clinician, patient)"
        )
    return actor


def roles_for_actors(actors: list[str]) -> frozenset[str]:
    allowed: set[str] = set()
    for actor in assigner_actors_from_jwt(actors):
        allowed.update(roles_for_actor(actor))
    return frozenset(allowed)


def validate_actor(actor: str) -> None:
    allowed = actor_classes()
    if actor not in allowed:
        raise ValueError(f"actor role must be one of {sorted(allowed)}")


def validate_roles(roles: list[str]) -> None:
    unknown = sorted(set(roles) - role_ids())
    if unknown:
        raise ValueError(f"unknown roles: {unknown}")


def validate_roles_for_assigner_actors(
    roles: list[str],
    assigner_actor_list: list[str],
) -> None:
    actors = assigner_actors_from_jwt(assigner_actor_list)
    validate_roles(roles)
    allowed = roles_for_actors(actors)
    disallowed = sorted(set(roles) - allowed)
    if disallowed:
        namespaces = ", ".join(actors)
        raise ValueError(
            "roles must use a tenant type allowed by your Tier-1 JWT roles "
            f"({namespaces}); disallowed: {disallowed}"
        )


def role_short_names(full_slugs: list[str], tenant_type: str) -> list[str]:
    """Strip tenant-type prefix for Cedar roles / JWT neosofia:roles."""
    prefix = f"{tenant_type}."
    names: list[str] = []
    seen: set[str] = set()
    for slug in full_slugs:
        if slug.startswith(prefix):
            name = slug[len(prefix) :]
        elif "." not in slug:
            name = slug
        else:
            continue
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
