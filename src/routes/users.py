from __future__ import annotations

import uuid as _uuid

from authorization_in_the_middle.security import with_security
from flask import Blueprint, jsonify, request

from src.authorization import entities as auth_entities
from src.bootstrap.capabilities import Capabilities
from src.bootstrap.config import settings
from src.bootstrap.logging_config import log_event
from src.db.engine import SessionLocal
from src.domain.role_catalog import validate_platform_roles_for_assigner_tiers
from src.services import user_service

bp = Blueprint("users", __name__, url_prefix="/api/v1/users")

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100
_SELF_FIELDS = frozenset({"first_name", "last_name", "email"})
_IMMUTABLE_FIELDS = frozenset({"uuid", "idp_id", "actor_class"})
_UNSUPPORTED_SCOPE_FIELDS = frozenset({
    "site_uuid",
    "site_group_uuid",
    "authorized_study_ids",
})
_PROVISION_FIELDS = frozenset({"tenant_uuid", "idp_id", "first_name", "last_name", "email"})


def _parse_pagination() -> tuple[int, int] | tuple[None, tuple]:
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(
            _MAX_PAGE_SIZE,
            max(1, int(request.args.get("page_size", _DEFAULT_PAGE_SIZE))),
        )
    except (TypeError, ValueError):
        return None, (
            jsonify({"error": "invalid_request", "message": "page and page_size must be integers"}),
            400,
        )
    return (page, page_size), None


def _reject_immutable_fields(data: dict) -> str | None:
    present = _IMMUTABLE_FIELDS.intersection(data.keys())
    if present:
        return f"fields are immutable: {sorted(present)}"
    return None


def _reject_unsupported_scope_fields(data: dict) -> str | None:
    present = _UNSUPPORTED_SCOPE_FIELDS.intersection(data.keys())
    if present:
        return (
            "site and study scope belong in domain services, not the user registry; "
            f"remove: {sorted(present)}"
        )
    return None


def _validate_update_payload(data: dict, *, self_service: bool) -> str | None:
    if not data:
        return "empty body"
    message = _reject_immutable_fields(data)
    if message:
        return message
    message = _reject_unsupported_scope_fields(data)
    if message:
        return message
    if self_service:
        extra = set(data.keys()) - _SELF_FIELDS
        if extra:
            return (
                f"self-service update allows only {sorted(_SELF_FIELDS)}; "
                f"remove: {sorted(extra)}"
            )
        return None
    if "platform_roles" in data:
        try:
            validate_platform_roles_for_assigner_tiers(
                list(data["platform_roles"] or []),
                auth_entities.principal_tier1_roles(),
            )
        except ValueError as exc:
            return str(exc)
    if "tenant_uuid" in data:
        try:
            _uuid.UUID(str(data["tenant_uuid"]))
        except ValueError:
            return "tenant_uuid must be a UUID"
    return None


def _validate_provision_payload(user_id: str, data: dict) -> str | None:
    try:
        _uuid.UUID(str(user_id))
    except ValueError:
        return "user_id must be a UUID"
    if not isinstance(data, dict) or not data:
        return "body must be a JSON object"
    missing = sorted(_PROVISION_FIELDS - data.keys())
    if missing:
        return f"missing required fields: {missing}"
    extra = sorted(set(data.keys()) - _PROVISION_FIELDS)
    if extra:
        return f"unsupported fields: {extra}"
    try:
        _uuid.UUID(str(data["tenant_uuid"]))
    except ValueError:
        return "tenant_uuid must be a UUID"
    if not str(data.get("idp_id") or "").strip():
        return "idp_id is required"
    for field in ("first_name", "last_name", "email"):
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            return f"{field} must be a string or null"
    return None


def _provision_entities() -> list[dict]:
    return [
        auth_entities.resolve_principal(),
        auth_entities.build_user_provisioning_entity(),
    ]


def _provision_resource() -> str:
    return f'{auth_entities.NAMESPACE}::UserProvisioning::"{auth_entities.USER_PROVISIONING_ID}"'


def init_user_routes(app, cedar_evaluator) -> None:
    app.extensions["cedar_evaluator"] = cedar_evaluator
    app.register_blueprint(bp)


@bp.route("", methods=["GET"])
@with_security(action=Capabilities.USER_LIST, rate_limit=settings.user_read_rate_limit)
def list_users():
    pagination, error = _parse_pagination()
    if error:
        return error
    page, page_size = pagination
    search = (request.args.get("q", "") or "").strip()
    try:
        with SessionLocal() as db:
            items, total = user_service.list_users(db, page, page_size, search)
            return jsonify({"items": items, "total": total, "page": page, "page_size": page_size}), 200
    except Exception as exc:
        log_event("list_users_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500


@bp.route("/<user_id>", methods=["GET"])
@with_security(action=Capabilities.USER_READ, rate_limit=settings.user_read_rate_limit)
def get_user(user_id: str):
    return jsonify(user_service.get_user_or_404(user_id)), 200


@bp.route("/<user_id>", methods=["PATCH"])
@with_security(action=Capabilities.USER_UPDATE, rate_limit=settings.user_write_rate_limit)
def patch_user(user_id: str):
    data = request.get_json(silent=True) or {}
    self_service = (
        auth_entities.principal_sub() == user_id and not auth_entities.principal_is_operator()
    )
    try:
        message = _validate_update_payload(data, self_service=self_service)
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
    if message:
        return jsonify({"error": "invalid_request", "message": message}), 400
    actor = auth_entities.principal_sub()
    try:
        with SessionLocal() as db:
            item = user_service.update_user(
                db,
                actor,
                user_id,
                data,
                self_service=self_service,
            )
            log_event("user_updated", actor_uuid=actor, user_uuid=user_id)
            return jsonify(item), 200
    except user_service.ConflictError:
        return jsonify({"error": "conflict", "message": "user update conflict"}), 409
    except Exception as exc:
        log_event("patch_user_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500


@bp.route("/<user_id>/audits", methods=["GET"])
@with_security(action=Capabilities.USER_READ, rate_limit=settings.user_read_rate_limit)
def get_user_audits(user_id: str):
    pagination, error = _parse_pagination()
    if error:
        return error
    page, page_size = pagination
    try:
        with SessionLocal() as db:
            items, total = user_service.get_user_audits(db, user_id, page, page_size)
            return jsonify({
                "user_uuid": user_id,
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }), 200
    except Exception as exc:
        log_event("get_user_audits_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500


@bp.route("/<user_id>", methods=["PUT"])
@with_security(
    action=Capabilities.USER_PROVISION,
    resource_fn=_provision_resource,
    entities_fn=_provision_entities,
    enforce_active_role=False,
    rate_limit=settings.user_write_rate_limit,
)
def provision_user(user_id: str):
    data = request.get_json(silent=True) or {}
    message = _validate_provision_payload(user_id, data)
    if message:
        return jsonify({"error": "invalid_request", "message": message}), 400
    try:
        with SessionLocal() as db:
            item, created = user_service.provision_user_identity(db, user_id, data)
            log_event("user_provisioned", user_uuid=user_id, created=created)
            return jsonify(item), 201 if created else 200
    except user_service.ConflictError:
        return jsonify({"error": "conflict", "message": "user provisioning conflict"}), 409
    except Exception as exc:
        log_event("provision_user_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500
