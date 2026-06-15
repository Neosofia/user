from __future__ import annotations

import uuid as _uuid

from authorization_in_the_middle.flask_identity import jwt_claim_principal_attributes
from authorization_in_the_middle.security import with_security
from flask import Blueprint, g, jsonify, request
from werkzeug.exceptions import NotFound

from src.authorization import entities as auth_entities
from src.bootstrap.config import settings
from src.bootstrap.logging_config import log_event
from src.db.engine import SessionLocal
from src.services import user_service

bp = Blueprint("users", __name__, url_prefix="/api/v1/users")
tenant_users_bp = Blueprint("tenant_users", __name__, url_prefix="/api/v1/tenants")

_DEFAULT_PAGE_SIZE = 15
_MAX_PAGE_SIZE = 100


def _jwt_sub() -> str:
    sub, _, jwt_attrs = jwt_claim_principal_attributes(g.jwt_claims)
    return str(jwt_attrs.get("uuid") or sub)


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


def _parse_tenant_uuid(tenant_uuid: str) -> str | None:
    try:
        return str(_uuid.UUID(str(tenant_uuid)))
    except ValueError:
        return None


def init_user_routes(app, cedar_evaluator) -> None:
    app.extensions["cedar_evaluator"] = cedar_evaluator
    app.register_blueprint(bp)
    app.register_blueprint(tenant_users_bp)


@bp.route("", methods=["GET"])
@with_security(rate_limit=settings.user_read_rate_limit)
def list_users_platform_catalog():
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


@tenant_users_bp.route("/<tenant_uuid>/users", methods=["GET"])
@with_security(rate_limit=settings.user_read_rate_limit)
def list_tenant_users(tenant_uuid: str):
    parsed_tenant = _parse_tenant_uuid(tenant_uuid)
    if parsed_tenant is None:
        return jsonify({"error": "invalid_request", "message": "tenant_uuid must be a UUID"}), 400
    pagination, error = _parse_pagination()
    if error:
        return error
    page, page_size = pagination
    search = (request.args.get("q", "") or "").strip()
    try:
        with SessionLocal() as db:
            items, total = user_service.list_users(
                db,
                page,
                page_size,
                search,
                tenant_uuid=parsed_tenant,
            )
            return jsonify({
                "tenant_uuid": parsed_tenant,
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }), 200
    except Exception as exc:
        log_event("list_tenant_users_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500


@bp.route("", methods=["POST"])
@with_security(rate_limit=settings.user_write_rate_limit)
def create_user():
    write_record = g.write_resource
    actor = _jwt_sub()
    try:
        with SessionLocal() as db:
            item, created = user_service.create_user(db, actor, write_record)
            return jsonify(item), 201 if created else 200
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
    except user_service.ConflictError as exc:
        return jsonify({"error": "conflict", "message": str(exc)}), 409
    except Exception as exc:
        log_event("create_user_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500


@bp.route("/<user_uuid>", methods=["GET"])
@with_security(
    rate_limit=settings.user_read_rate_limit,
    resource_loader=lambda user_uuid: user_service.get_user_or_404(user_uuid),
)
def get_user(user_uuid: str):
    return jsonify(user_service.get_user_or_404(user_uuid)), 200


@bp.route("/<user_uuid>", methods=["PATCH"])
@with_security(
    rate_limit=settings.user_write_rate_limit,
    resource_loader=lambda user_uuid: user_service.get_user_or_404(user_uuid),
)
def patch_user(user_uuid: str):
    immutable = sorted(user_service.PATCH_CEDAR_ONLY_FIELDS & g.validated_body.keys())
    if immutable:
        return jsonify({
            "error": "invalid_request",
            "message": f"field(s) not mutable via PATCH: {', '.join(immutable)}",
        }), 400

    actor = _jwt_sub()
    try:
        with SessionLocal() as db:
            item = user_service.update_user(db, actor, user_uuid, g.patch_body)
            log_event("user_updated", actor_uuid=actor, user_uuid=user_uuid)
            return jsonify(item), 200
    except NotFound:
        return jsonify({"error": "not_found"}), 404
    except user_service.ConflictError as exc:
        return jsonify({"error": "conflict", "message": str(exc)}), 409
    except Exception as exc:
        log_event("patch_user_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500


@bp.route("/<user_uuid>/audits", methods=["GET"])
@with_security(
    rate_limit=settings.user_read_rate_limit,
    resource_loader=lambda user_uuid: user_service.get_user_or_404(user_uuid),
)
def get_user_audits(user_uuid: str):
    pagination, error = _parse_pagination()
    if error:
        return error
    page, page_size = pagination
    try:
        with SessionLocal() as db:
            items, total = user_service.get_user_audits(db, user_uuid, page, page_size)
            return jsonify({
                "user_uuid": user_uuid,
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }), 200
    except Exception as exc:
        log_event("get_user_audits_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500


@bp.route("/<user_uuid>", methods=["PUT"])
@with_security(
    action='Action::"user:provision"',
    resource_type="UserProvisioning",
    catalog_id=auth_entities.USER_PROVISIONING_ID,
    enforce_active_actor=False,
    validate_openapi=True,
    rate_limit=settings.user_write_rate_limit,
)
def provision_user(user_uuid: str):
    payload = g.validated_body
    try:
        with SessionLocal() as db:
            item, created = user_service.provision_user_identity(db, user_uuid, payload)
            log_event("user_provisioned", user_uuid=user_uuid, created=created)
            return jsonify(item), 201 if created else 200
    except user_service.ConflictError as exc:
        return jsonify({"error": "conflict", "message": str(exc)}), 409
    except Exception as exc:
        log_event("provision_user_failed", error_type=type(exc).__name__)
        return jsonify({"error": "database error"}), 500
