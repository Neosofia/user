from authorization_in_the_middle.security import with_security
from flask import Blueprint, jsonify

from src.authorization.entities import tier1_actor_classes
from src.bootstrap.config import settings
from src.services.role_catalog import (
    role_definition,
    role_ids,
    tenant_type_roles,
)

bp = Blueprint("roles", __name__, url_prefix="/api/v1/roles")


@bp.route("", methods=["GET"])
@with_security(action='Action::"role_catalog:read"', rate_limit=settings.user_read_rate_limit)
def list_roles():
    roles = sorted(role_ids())
    return jsonify({
        "actor_classes": sorted(tier1_actor_classes()),
        "roles": roles,
        "role_definitions": [role_definition(role_id) for role_id in roles],
        "tenant_types": {
            tenant_type: sorted(roles)
            for tenant_type, roles in sorted(tenant_type_roles().items())
        },
    }), 200
