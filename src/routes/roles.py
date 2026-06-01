from authorization_in_the_middle.security import with_security
from flask import Blueprint, jsonify

from src.authorization import entities as auth_entities
from src.bootstrap.capabilities import Capabilities
from src.bootstrap.config import settings
from src.domain.role_catalog import (
    ACTOR_CLASSES,
    assigner_actors,
    roles_for_actors,
    tenant_type_roles,
)

bp = Blueprint("roles", __name__, url_prefix="/api/v1/roles")


@bp.route("", methods=["GET"])
@with_security(action=Capabilities.ROLE_CATALOG_READ, rate_limit=settings.user_read_rate_limit)
def list_roles():
    actors = auth_entities.principal_actors()
    if not actors:
        return jsonify({
            "error": "invalid_request",
            "message": "JWT must include at least one Tier-1 role (operator, clinician, patient)",
        }), 400
    roles = sorted(roles_for_actors(actors))
    return jsonify({
        "actor_classes": sorted(ACTOR_CLASSES),
        "roles": roles,
        "tenant_types": {
            tenant_type: sorted(roles)
            for tenant_type, roles in sorted(tenant_type_roles().items())
        },
        "assigner_actor_prefixes": {
            actor: list(prefixes)
            for actor, prefixes in sorted(assigner_actors().items())
            if actor in actors
        },
        "assigner_actors": actors,
    }), 200
