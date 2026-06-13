"""Cedar entity wiring for the user service."""
from __future__ import annotations

from typing import Any

from authentication_in_the_middle.actors import ensure_tier1_actor_classes
from authorization_in_the_middle.cedar_attrs import tier1_actor_flags as cedar_tier1_flags
from authorization_in_the_middle.entities import (
    ID_PLACEHOLDER,
    build_catalog_entity,
    build_entity_payload,
    catalog_entities,
    catalog_resource_uid,
    resolve_entity_id,
)
from authorization_in_the_middle.flask_identity import jwt_claim_principal_attributes
from flask import g, request
from werkzeug.exceptions import NotFound

NAMESPACE = "users"
USER_CATALOG_ID = "user-catalog"
ROLE_CATALOG_ID = "role-catalog"
USER_PROVISIONING_ID = "user-provisioning"

_DEFAULT_TIER1_ACTORS = frozenset({"operator", "study", "clinician", "patient", "demo"})


def tier1_actor_classes() -> frozenset[str]:
    from flask import current_app, has_app_context

    if has_app_context():
        return ensure_tier1_actor_classes(current_app)
    return _DEFAULT_TIER1_ACTORS


def registry_user_cedar_attrs(row: dict[str, Any]) -> dict[str, Any]:
    """Cedar resource attrs for a registry row (full role slugs on ``roles``)."""
    return {
        "uuid": str(row.get("uuid") or ""),
        "tenantId": str(row.get("tenant_uuid") or ""),
        "roles": list(row.get("roles") or []),
        "tokenType": "human",
    }


def principal_cedar_attrs(row: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
    """Cedar principal attrs for the caller (JWT short roles + tier-1 flags)."""
    _, _, jwt_attrs = jwt_claim_principal_attributes(claims)
    actors = jwt_attrs.get("actors")
    jwt_actors = actors if isinstance(actors, list) else []
    jwt_roles = jwt_attrs.get("roles")
    roles = (
        [str(role) for role in jwt_roles if str(role).strip()]
        if isinstance(jwt_roles, list)
        else []
    )
    token_type = jwt_attrs.get("tokenType") or jwt_attrs.get("token_type") or "human"
    return {
        "uuid": str(row.get("uuid") or jwt_attrs.get("uuid") or claims.get("sub", "")),
        "tenantId": str(row.get("tenant_uuid") or jwt_attrs.get("tenantId") or ""),
        "tenantType": str(jwt_attrs.get("tenantType") or ""),
        "roles": roles,
        "tokenType": str(token_type),
        **cedar_tier1_flags(jwt_actors, tier1_actor_classes()),
    }


def build_user_entity(entity_id: str, attrs: dict[str, Any]) -> dict[str, Any]:
    """Manual Cedar entity for policy unit tests."""
    return build_entity_payload(f"{NAMESPACE}::User", entity_id, attrs)


def resolve_user_entity_id(record: dict[str, Any], fallback_id: str | None = None) -> str:
    return resolve_entity_id(record, "uuid", fallback_id or ID_PLACEHOLDER)


def resolve_principal() -> dict[str, Any]:
    from src.services import user_service

    claims = g.jwt_claims
    sub, _, jwt_attrs = jwt_claim_principal_attributes(claims)
    principal_id = str(jwt_attrs.get("uuid") or sub)
    token_type = str(jwt_attrs.get("token_type") or claims.get("token_type") or "human")
    if token_type == "service":
        return build_entity_payload(
            f"{NAMESPACE}::Service",
            principal_id,
            {"serviceSlug": principal_id, "tokenType": token_type},
        )
    try:
        row = user_service.get_user_or_404(principal_id)
        entity_id = row["uuid"]
    except NotFound:
        row = {
            "uuid": sub,
            "tenant_uuid": str(jwt_attrs.get("tenantId") or ""),
            "roles": [],
        }
        entity_id = sub
    return build_entity_payload(
        f"{NAMESPACE}::User",
        entity_id,
        principal_cedar_attrs(row, claims),
    )


def build_user_resource_entity(
    user_uuid: str,
    row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = row or {"uuid": user_uuid, "tenant_uuid": "", "roles": []}
    entity_id = str(row.get("uuid") or user_uuid)
    return build_entity_payload(
        f"{NAMESPACE}::User",
        entity_id,
        registry_user_cedar_attrs(row),
    )


def build_write_user_entity(record: dict[str, Any]) -> dict[str, Any]:
    entity_id = resolve_user_entity_id(record)
    return build_user_resource_entity(entity_id, {**record, "uuid": entity_id})


def build_user_catalog_entity() -> dict[str, Any]:
    return build_catalog_entity(NAMESPACE, "UserCatalog", USER_CATALOG_ID)


def build_tenant_user_catalog_entity(tenant_uuid: str) -> dict[str, Any]:
    tenant_id = str(tenant_uuid)
    return build_catalog_entity(NAMESPACE, "UserCatalog", tenant_id, {"tenantId": tenant_id})


def tenant_user_catalog_resource_uid() -> str:
    return catalog_resource_uid(NAMESPACE, "UserCatalog", str(request.view_args["tenant_uuid"]))


def tenant_user_list_entities() -> list[dict[str, Any]]:
    tenant_uuid = str(request.view_args["tenant_uuid"])
    return catalog_entities(
        resolve_principal,
        lambda: build_tenant_user_catalog_entity(tenant_uuid),
    )


def build_role_catalog_entity() -> dict[str, Any]:
    return build_catalog_entity(NAMESPACE, "RoleCatalog", ROLE_CATALOG_ID)


def build_user_provisioning_entity() -> dict[str, Any]:
    return build_catalog_entity(NAMESPACE, "UserProvisioning", USER_PROVISIONING_ID)


def user_provisioning_resource_uid() -> str:
    return catalog_resource_uid(NAMESPACE, "UserProvisioning", USER_PROVISIONING_ID)


def user_provisioning_entities() -> list[dict[str, Any]]:
    return catalog_entities(resolve_principal, build_user_provisioning_entity)
