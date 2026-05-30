"""File-backed platform role catalog with optional deploy-time overlay."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.bootstrap.config import settings

TIER1_ACTOR_CLASSES: frozenset[str] = frozenset({"operator", "clinician", "patient"})
DEFAULT_ROLE_CATALOG_PATH = Path(__file__).resolve().parents[2] / "roles" / "default.json"


@dataclass(frozen=True)
class RoleCatalog:
    platform_roles: frozenset[str]
    assigner_prefixes: dict[str, tuple[str, ...]]


def _role_id(value: object) -> str:
    if isinstance(value, str):
        role_id = value.strip()
    elif isinstance(value, dict):
        role_id = str(value.get("id", "")).strip()
    else:
        role_id = ""
    if not role_id or any(char.isspace() for char in role_id) or "." not in role_id:
        raise ValueError(f"invalid platform role id: {value!r}")
    return role_id


def _prefixes(value: object, tier1: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"assigner_prefixes.{tier1} must be a list")
    prefixes: list[str] = []
    seen: set[str] = set()
    for raw in value:
        prefix = str(raw).strip()
        if not prefix or any(char.isspace() for char in prefix) or not prefix.endswith("."):
            raise ValueError(f"invalid assigner prefix for {tier1}: {raw!r}")
        if prefix not in seen:
            seen.add(prefix)
            prefixes.append(prefix)
    return tuple(prefixes)


def _catalog_from_mapping(data: dict[str, Any], source: Path) -> RoleCatalog:
    raw_roles = data.get("roles")
    if not isinstance(raw_roles, list):
        raise ValueError(f"{source} must contain a roles list")
    roles = frozenset(_role_id(role) for role in raw_roles)

    raw_prefixes = data.get("assigner_prefixes", {})
    if not isinstance(raw_prefixes, dict):
        raise ValueError(f"{source} assigner_prefixes must be an object")
    prefixes: dict[str, tuple[str, ...]] = {}
    for tier1, raw_value in raw_prefixes.items():
        tier1_key = str(tier1).strip()
        validate_tier1_actor(tier1_key)
        prefixes[tier1_key] = _prefixes(raw_value, tier1_key)
    return RoleCatalog(platform_roles=roles, assigner_prefixes=prefixes)


def load_catalog_file(path: Path) -> RoleCatalog:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    return _catalog_from_mapping(data, path)


def merge_catalogs(default: RoleCatalog, overlay: RoleCatalog | None) -> RoleCatalog:
    if overlay is None:
        return default
    prefixes: dict[str, list[str]] = {
        tier1: list(values) for tier1, values in default.assigner_prefixes.items()
    }
    for tier1, values in overlay.assigner_prefixes.items():
        existing = prefixes.setdefault(tier1, [])
        for prefix in values:
            if prefix not in existing:
                existing.append(prefix)
    return RoleCatalog(
        platform_roles=frozenset(default.platform_roles | overlay.platform_roles),
        assigner_prefixes={tier1: tuple(values) for tier1, values in prefixes.items()},
    )


@lru_cache(maxsize=1)
def role_catalog() -> RoleCatalog:
    default = load_catalog_file(DEFAULT_ROLE_CATALOG_PATH)
    overlay_path = settings.role_catalog_overlay
    overlay = load_catalog_file(overlay_path) if overlay_path else None
    return merge_catalogs(default, overlay)


def platform_role_ids() -> frozenset[str]:
    return role_catalog().platform_roles


def assigner_prefixes() -> dict[str, tuple[str, ...]]:
    return role_catalog().assigner_prefixes


def platform_roles_for_tier1(tier1: str) -> frozenset[str]:
    prefixes = assigner_prefixes().get(tier1, ())
    return frozenset(
        role for role in platform_role_ids() if any(role.startswith(prefix) for prefix in prefixes)
    )


def assigner_tier1_roles_from_jwt(roles: list[str]) -> list[str]:
    """Distinct Tier-1 roles from JWT, preserving claim order."""
    tier1: list[str] = []
    seen: set[str] = set()
    for role in roles:
        if role in TIER1_ACTOR_CLASSES and role not in seen:
            seen.add(role)
            tier1.append(role)
    if not tier1:
        raise ValueError(
            "JWT must include at least one Tier-1 role (operator, clinician, patient)"
        )
    return tier1


def platform_roles_for_tier1_roles(tier1_roles: list[str]) -> frozenset[str]:
    allowed: set[str] = set()
    for tier1 in assigner_tier1_roles_from_jwt(tier1_roles):
        allowed.update(platform_roles_for_tier1(tier1))
    return frozenset(allowed)


def validate_tier1_actor(tier1: str) -> None:
    if tier1 not in TIER1_ACTOR_CLASSES:
        raise ValueError(f"tier1 role must be one of {sorted(TIER1_ACTOR_CLASSES)}")


def validate_platform_roles(platform_roles: list[str]) -> None:
    unknown = sorted(set(platform_roles) - platform_role_ids())
    if unknown:
        raise ValueError(f"unknown platform_roles: {unknown}")


def validate_platform_roles_for_assigner(platform_roles: list[str], assigner_tier1: str) -> None:
    validate_platform_roles_for_assigner_tiers(platform_roles, [assigner_tier1])


def validate_platform_roles_for_assigner_tiers(
    platform_roles: list[str],
    assigner_tier1_roles: list[str],
) -> None:
    tier1_roles = assigner_tier1_roles_from_jwt(assigner_tier1_roles)
    validate_platform_roles(platform_roles)
    allowed = platform_roles_for_tier1_roles(tier1_roles)
    disallowed = sorted(set(platform_roles) - allowed)
    if disallowed:
        namespaces = ", ".join(tier1_roles)
        raise ValueError(
            "platform_roles must use a namespace allowed by your Tier-1 JWT roles "
            f"({namespaces}); disallowed: {disallowed}"
        )
