from authorization_in_the_middle.security import with_security
from flask import Blueprint, jsonify

from src.authorization import entities as auth_entities
from src.bootstrap.capabilities import Capabilities
from src.bootstrap.config import settings
from src.domain.role_catalog import (
    TIER1_ACTOR_CLASSES,
    assigner_prefixes,
    platform_roles_for_tier1_roles,
)

bp = Blueprint("roles", __name__, url_prefix="/api/v1/roles")


@bp.route("", methods=["GET"])
@with_security(action=Capabilities.ROLE_CATALOG_READ, rate_limit=settings.user_read_rate_limit)
def list_roles():
    tier1_roles = auth_entities.principal_tier1_roles()
    if not tier1_roles:
        return jsonify({
            "error": "invalid_request",
            "message": "JWT must include at least one Tier-1 role (operator, clinician, patient)",
        }), 400
    roles = sorted(platform_roles_for_tier1_roles(tier1_roles))
    return jsonify({
        "actor_classes": sorted(TIER1_ACTOR_CLASSES),
        "platform_roles": roles,
        "assigner_prefixes": {
            tier1: list(prefixes)
            for tier1, prefixes in sorted(assigner_prefixes().items())
            if tier1 in tier1_roles
        },
        "assigner_tier1_roles": tier1_roles,
    }), 200
