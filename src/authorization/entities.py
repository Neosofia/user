"""Cedar entity wiring for the user service."""
from __future__ import annotations

from typing import Any

from authentication_in_the_middle.actors import ensure_tier1_actor_classes
from authorization_in_the_middle.flask_identity import resolve_jwt_principal
from flask import current_app, has_app_context

NAMESPACE = "users"
USER_PROVISIONING_ID = "user-provisioning"

_DEFAULT_TIER1_ACTORS = frozenset({"operator", "study", "clinician", "patient", "demo"})


def tier1_actor_classes() -> frozenset[str]:
    if has_app_context():
        return ensure_tier1_actor_classes(current_app)
    return _DEFAULT_TIER1_ACTORS


def registry_user_cedar_attrs(row: dict[str, Any]) -> dict[str, Any]:
    """Map registry rows to Cedar member attrs (SDK synthesizes builders from this)."""
    return {
        "uuid": str(row.get("uuid") or ""),
        "tenantId": str(row.get("tenant_uuid") or ""),
        "roles": list(row.get("roles") or []),
        "tokenType": "human",
    }


def resolve_principal() -> dict[str, Any]:
    return resolve_jwt_principal(NAMESPACE, actor_classes=tier1_actor_classes())
