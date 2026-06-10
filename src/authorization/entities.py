"""
Cedar entity builders and per-route entity sets for the user service.

This service authorizes user-registry operations:

| Route | Action | Resource |
|-------|--------|----------|
| GET/PATCH /api/v1/users/{user_uuid} | user:read, user:update | users::User (target row) |
| GET /api/v1/users | user:list | users::UserCatalog |
| POST /api/v1/users | user:create | users::UserCatalog |
| GET /api/v1/roles | role_catalog:read | users::RoleCatalog |
| PUT /api/v1/users/{user_uuid} | user:provision | users::UserProvisioning |
"""
from __future__ import annotations

from typing import Any

from authorization_in_the_middle.entities import build_entity_payload, entity_uid
from flask import g, request
from werkzeug.exceptions import NotFound

from src.bootstrap.config import settings
from src.domain.role_catalog import role_short_names

NAMESPACE = "users"
USER_CATALOG_ID = "user-catalog"
ROLE_CATALOG_ID = "role-catalog"
USER_PROVISIONING_ID = "user-provisioning"


def _jwt_claim(name: str) -> str:
    return f"{settings.jwt_claim_namespace}:{name}"


def resolve_principal() -> dict[str, Any]:
    from src.services import user_service

    claims = _claims()
    sub = principal_sub()
    if principal_token_type() == "service":
        return build_service_principal_entity(sub, claims)
    try:
        return build_principal_entity(user_service.get_user_or_404(sub), claims)
    except NotFound:
        return _principal_from_claims(claims)


def principal_sub() -> str:
    return str(_claims()["sub"])


def principal_is_operator() -> bool:
    """True when Cedar would set isOperator (operator actor on the JWT)."""
    return "operator" in _jwt_active_actors(_claims())


def principal_tenant_uuid() -> str | None:
    """Tenant UUID for the authenticated principal (JWT claim or registry row)."""
    claims = _claims()
    claim_tenant = claims.get(_jwt_claim("tenant_uuid"))
    if claim_tenant:
        return str(claim_tenant)
    if principal_token_type() == "service":
        return None
    from src.services import user_service

    try:
        return user_service.get_user_or_404(principal_sub())["tenant_uuid"]
    except NotFound:
        return None


def principal_token_type() -> str:
    claims = _claims()
    return str(claims.get(_jwt_claim("token_type")) or claims.get("token_type") or "human")


def _claims() -> dict[str, Any]:
    claims = getattr(g, "jwt_claims", {})
    sub = claims.get("sub")
    if not sub:
        raise ValueError("missing sub")
    return claims


def _jwt_list(claims: dict[str, Any], claim_key: str) -> list[str]:
    value = claims.get(claim_key, [])
    return value if isinstance(value, list) else []


def _jwt_active_actors(claims: dict[str, Any]) -> list[str]:
    return _jwt_list(claims, _jwt_claim("actors"))


def principal_actors() -> list[str]:
    """
    Actor classes for role assignment.

    Uses the full session list (``JWT_CLAIM_NAMESPACE:session_actors``) when the auth
    middleware has narrowed the active actor to the UI selection.
    """
    from src.domain.role_catalog import actor_classes

    claims = _claims()
    session_actors = _jwt_list(claims, _jwt_claim("session_actors"))
    source = session_actors if session_actors else _jwt_active_actors(claims)
    allowed = actor_classes()
    actors: list[str] = []
    seen: set[str] = set()
    for actor in source:
        if actor in allowed and actor not in seen:
            seen.add(actor)
            actors.append(actor)
    return actors


def tenant_type_for_row(row: dict[str, Any], claims: dict[str, Any] | None = None) -> str:
    return _tenant_type(row, claims or _claims())


_STUDY_TENANT_TYPES = frozenset({"cro", "sponsor", "smo"})
_PLATFORM_PREFIX = "platform."
_SITE_PREFIX = "site."
_PATIENT_PREFIX = "patient."
_STUDY_PREFIXES = tuple(f"{tenant}." for tenant in sorted(_STUDY_TENANT_TYPES))


def _active_org_role_slug() -> str | None:
    slug = (request.headers.get("X-Active-Org-Role") or "").strip()
    if slug and "." in slug:
        return slug
    return None


def _resolve_org_role_slug(
    row: dict[str, Any],
    header_slug: str | None,
    prefixes: tuple[str, ...],
) -> str | None:
    if header_slug and any(header_slug.startswith(prefix) for prefix in prefixes):
        return header_slug
    for candidate in row.get("roles") or []:
        text = str(candidate).strip()
        if "." in text and any(text.startswith(prefix) for prefix in prefixes):
            return text
    return None


def _org_role_context_from_slug(slug: str, allowed_tenant_types: frozenset[str]) -> tuple[str, list[str]] | None:
    tenant_type, _, short = slug.partition(".")
    if tenant_type not in allowed_tenant_types or not short:
        return None
    return tenant_type, [short]


def _study_authorization_context(
    row: dict[str, Any],
    jwt_actors: list[str],
) -> tuple[str, list[str]] | None:
    """When study is active, authorize using the selected CRO/sponsor/SMO org role."""
    if "study" not in jwt_actors:
        return None
    slug = _resolve_org_role_slug(row, _active_org_role_slug(), _STUDY_PREFIXES)
    if not slug:
        return None
    return _org_role_context_from_slug(slug, _STUDY_TENANT_TYPES)


def _operator_authorization_context(
    row: dict[str, Any],
    jwt_actors: list[str],
) -> tuple[str, list[str]] | None:
    """When operator is active, authorize using the selected platform org role."""
    if "operator" not in jwt_actors:
        return None
    slug = _resolve_org_role_slug(row, _active_org_role_slug(), (_PLATFORM_PREFIX,))
    if not slug:
        return None
    return _org_role_context_from_slug(slug, frozenset({"platform"}))


def _site_authorization_context(
    row: dict[str, Any],
    jwt_actors: list[str],
) -> tuple[str, list[str]] | None:
    """When clinician is active, authorize using the selected site org role."""
    if "clinician" not in jwt_actors:
        return None
    slug = _resolve_org_role_slug(row, _active_org_role_slug(), (_SITE_PREFIX,))
    if not slug:
        return None
    return _org_role_context_from_slug(slug, frozenset({"site"}))


def _patient_authorization_context(
    row: dict[str, Any],
    jwt_actors: list[str],
) -> tuple[str, list[str]] | None:
    """When patient is active, authorize using the selected patient org role."""
    if "patient" not in jwt_actors:
        return None
    slug = _resolve_org_role_slug(row, _active_org_role_slug(), (_PATIENT_PREFIX,))
    if not slug:
        return None
    return _org_role_context_from_slug(slug, frozenset({"patient"}))


def _session_org_role_context(
    row: dict[str, Any],
    jwt_actors: list[str],
) -> tuple[str, list[str]] | None:
    """Map the active Tier-1 actor + org role to Cedar tenantType and short role names."""
    for builder in (
        _study_authorization_context,
        _operator_authorization_context,
        _site_authorization_context,
        _patient_authorization_context,
    ):
        ctx = builder(row, jwt_actors)
        if ctx:
            return ctx
    return None


def _tenant_type(row: dict[str, Any], claims: dict[str, Any]) -> str:
    session_ctx = _session_org_role_context(row, _jwt_active_actors(claims))
    if session_ctx:
        return session_ctx[0]
    for slug in row.get("roles") or []:
        if "." in slug:
            return slug.split(".", 1)[0]
    claim_type = claims.get(_jwt_claim("tenant_type"))
    if claim_type:
        return str(claim_type)
    return "platform"


def _roles_for_cedar(
    row: dict[str, Any],
    claims: dict[str, Any],
    *,
    prefer_row_roles: bool = False,
) -> list[str]:
    jwt_actors = _jwt_active_actors(claims)
    session_ctx = _session_org_role_context(row, jwt_actors)
    if session_ctx:
        return session_ctx[1]
    tenant_type = _tenant_type(row, claims)
    if prefer_row_roles:
        return role_short_names(list(row.get("roles") or []), tenant_type)
    jwt_roles = _jwt_list(claims, _jwt_claim("roles"))
    if jwt_roles:
        return role_short_names([str(role) for role in jwt_roles if str(role).strip()], tenant_type)
    return role_short_names(list(row.get("roles") or []), tenant_type)


def _user_attrs(
    row: dict[str, Any],
    claims: dict[str, Any],
    *,
    prefer_row_roles: bool = False,
) -> dict[str, Any]:
    jwt_actors = _jwt_active_actors(claims)
    tenant_type = _tenant_type(row, claims)
    return {
        "uuid": row["uuid"],
        "tenantId": row["tenant_uuid"],
        "tenantType": tenant_type,
        "roles": _roles_for_cedar(row, claims, prefer_row_roles=prefer_row_roles),
        "actorClass": "",
        "tokenType": principal_token_type(),
        "isOperator": "operator" in jwt_actors,
        "isStudy": "study" in jwt_actors,
        "isClinician": "clinician" in jwt_actors,
    }


def _principal_from_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Principal for callers authenticated but not yet registered in the user registry."""
    sub = str(claims["sub"])
    jwt_actors = _jwt_active_actors(claims)
    tenant_uuid = claims.get(_jwt_claim("tenant_uuid")) or ""
    slug = _active_org_role_slug()
    if slug and "." in slug:
        inferred_type, _, short = slug.partition(".")
        if short and (
            ("operator" in jwt_actors and inferred_type == "platform")
            or ("clinician" in jwt_actors and inferred_type == "site")
            or ("patient" in jwt_actors and inferred_type == "patient")
            or ("study" in jwt_actors and inferred_type in _STUDY_TENANT_TYPES)
        ):
            tenant_type = inferred_type
            roles = [short]
        else:
            tenant_type = str(claims.get(_jwt_claim("tenant_type")) or "platform")
            roles = role_short_names(_jwt_list(claims, _jwt_claim("roles")), tenant_type)
    else:
        tenant_type = str(claims.get(_jwt_claim("tenant_type")) or "platform")
        roles = role_short_names(_jwt_list(claims, _jwt_claim("roles")), tenant_type)
    return build_entity_payload(
        f"{NAMESPACE}::User",
        sub,
        {
            "uuid": sub,
            "tenantId": str(tenant_uuid),
            "tenantType": tenant_type,
            "roles": roles,
            "actorClass": "operator" if "operator" in jwt_actors else "",
            "tokenType": principal_token_type(),
            "isOperator": "operator" in jwt_actors,
            "isStudy": "study" in jwt_actors,
            "isClinician": "clinician" in jwt_actors,
        },
    )


def build_service_principal_entity(service_slug: str, claims: dict[str, Any]) -> dict[str, Any]:
    return build_entity_payload(
        f"{NAMESPACE}::Service",
        service_slug,
        {
            "serviceSlug": service_slug,
            "tokenType": str(claims.get(_jwt_claim("token_type")) or claims.get("token_type") or ""),
        },
    )


def build_user_resource_entity(
    user_uuid: str,
    row: dict[str, Any] | None = None,
    claims: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_claims = claims or _claims()
    if row is None:
        row = {"uuid": user_uuid, "tenant_uuid": "", "roles": []}
    return build_entity_payload(
        f"{NAMESPACE}::User",
        user_uuid,
        _user_attrs(row, resolved_claims, prefer_row_roles=True),
    )


def build_principal_entity(row: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
    return build_entity_payload(
        f"{NAMESPACE}::User",
        row["uuid"],
        _user_attrs(row, claims, prefer_row_roles=False),
    )


def build_user_catalog_entity() -> dict[str, Any]:
    return build_entity_payload(f"{NAMESPACE}::UserCatalog", USER_CATALOG_ID, {})


def build_role_catalog_entity() -> dict[str, Any]:
    return build_entity_payload(f"{NAMESPACE}::RoleCatalog", ROLE_CATALOG_ID, {})


def build_user_provisioning_entity() -> dict[str, Any]:
    return build_entity_payload(f"{NAMESPACE}::UserProvisioning", USER_PROVISIONING_ID, {})


def user_provisioning_resource_uid() -> str:
    return entity_uid(f"{NAMESPACE}::UserProvisioning", USER_PROVISIONING_ID)


def user_provisioning_entities() -> list[dict[str, Any]]:
    return [resolve_principal(), build_user_provisioning_entity()]
