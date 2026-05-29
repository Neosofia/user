"""
Cedar entity builders and per-route entity sets for the user service.

Stage 2: registry rows are provisioned outside this API (see README). Stage 3 will
flip flow so authentication best-effort syncs into this service on login.

This service authorizes user-registry operations:

| Route | Action | Resource |
|-------|--------|----------|
| GET/PATCH /api/v1/users/{user_id} | user:read, user:update | users::User (target row) |
| GET /api/v1/users | user:list | users::UserCatalog |
| GET /api/v1/roles | role_catalog:read | users::RoleCatalog |
"""
from __future__ import annotations

from typing import Any

from authorization_in_the_middle.entities import build_entity_payload
from flask import g
from werkzeug.exceptions import NotFound

from src.bootstrap.config import settings

NAMESPACE = "users"
USER_CATALOG_ID = "user-catalog"
ROLE_CATALOG_ID = "role-catalog"


def _jwt_claim(name: str) -> str:
    return f"{settings.jwt_claim_namespace}:{name}"


def resolve_principal() -> dict[str, Any]:
    from src.services import user_service

    claims = _claims()
    sub = principal_sub()
    try:
        return build_principal_entity(user_service.get_user_or_404(sub), claims)
    except NotFound:
        return _principal_from_claims(claims)


def principal_sub() -> str:
    return str(_claims()["sub"])


def principal_is_operator() -> bool:
    """True when Cedar would set isOperator (Tier-1 operator on the JWT)."""
    return "operator" in _jwt_tier1_roles(_claims())


def _claims() -> dict[str, Any]:
    claims = getattr(g, "jwt_claims", {})
    sub = claims.get("sub")
    if not sub:
        raise ValueError("missing sub")
    return claims


def _jwt_role_list(claims: dict[str, Any], claim_key: str) -> list[str]:
    roles = claims.get(claim_key, [])
    return roles if isinstance(roles, list) else []


def _jwt_tier1_roles(claims: dict[str, Any]) -> list[str]:
    return _jwt_role_list(claims, _jwt_claim("roles"))


def principal_tier1_roles() -> list[str]:
    """
    Tier-1 roles for platform-role assignment.

    Uses the full session list (``JWT_CLAIM_NAMESPACE:session_roles``) when the auth
    middleware has narrowed the active-role claim to the UI selection.
    """
    from src.domain.role_catalog import TIER1_ACTOR_CLASSES

    claims = _claims()
    session_roles = _jwt_role_list(claims, _jwt_claim("session_roles"))
    source = session_roles if session_roles else _jwt_tier1_roles(claims)
    tier1: list[str] = []
    seen: set[str] = set()
    for role in source:
        if role in TIER1_ACTOR_CLASSES and role not in seen:
            seen.add(role)
            tier1.append(role)
    return tier1


def _user_attrs(row: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
    platform_roles = list(row.get("platform_roles") or [])
    jwt_roles = _jwt_tier1_roles(claims)
    return {
        "uuid": row["uuid"],
        "tenantId": row["tenant_uuid"],
        "actorClass": "",
        "isPlatformAdmin": "operator.platform-admin" in platform_roles,
        "isOperator": "operator" in jwt_roles,
    }


def _principal_from_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Principal for callers authenticated but not yet registered in the user registry."""
    sub = str(claims["sub"])
    jwt_roles = _jwt_tier1_roles(claims)
    tenant_uuid = claims.get(_jwt_claim("tenant_uuid")) or ""
    return build_entity_payload(
        f"{NAMESPACE}::User",
        sub,
        {
            "uuid": sub,
            "tenantId": str(tenant_uuid),
            "actorClass": "operator" if "operator" in jwt_roles else "",
            "isPlatformAdmin": False,
            "isOperator": "operator" in jwt_roles,
        },
    )


def build_user_resource_entity(
    user_id: str,
    row: dict[str, Any],
    claims: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_entity_payload(
        f"{NAMESPACE}::User",
        user_id,
        _user_attrs(row, claims or _claims()),
    )


def build_principal_entity(row: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
    return build_user_resource_entity(row["uuid"], row, claims)


def build_user_catalog_entity() -> dict[str, Any]:
    return build_entity_payload(f"{NAMESPACE}::UserCatalog", USER_CATALOG_ID, {})


def build_role_catalog_entity() -> dict[str, Any]:
    return build_entity_payload(f"{NAMESPACE}::RoleCatalog", ROLE_CATALOG_ID, {})


