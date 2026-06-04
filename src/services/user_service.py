from __future__ import annotations

import uuid as _uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound

from src.bootstrap.logging_config import log_event
from src.models.user import User, UserHistory


class ConflictError(Exception):
    """Registry write conflict (unique constraint or concurrent upsert)."""


def _display_code_conflict_message(display_code: str | None) -> str:
    if display_code:
        return (
            f"Display code {display_code!r} is already assigned to another patient "
            "in this organization. Use a different code or enroll the existing patient."
        )
    return "Display code is already in use for another patient in this organization."


def _integrity_conflict_message(exc: IntegrityError, *, display_code: str | None = None) -> str:
    detail = str(exc.orig).lower() if exc.orig else str(exc).lower()
    if "uq_users_tenant_display_code" in detail or (
        "display_code" in detail and "tenant_uuid" in detail
    ):
        return _display_code_conflict_message(display_code)
    if "idp_id" in detail:
        return "A user with this identity provider id already exists."
    if "users_pkey" in detail or "uuid" in detail and "unique" in detail:
        return "A user with this identifier already exists."
    return "A user with these details already exists in the registry."


def _display_code_in_use(
    db,
    tenant_id: _uuid.UUID,
    display_code: str | None,
    *,
    exclude_uuid: _uuid.UUID | None = None,
) -> bool:
    if not display_code:
        return False
    query = select(User.uuid).where(
        User.tenant_uuid == tenant_id,
        User.display_code == display_code,
    )
    if exclude_uuid is not None:
        query = query.where(User.uuid != exclude_uuid)
    return db.scalar(query) is not None


SYSTEM_ACTOR_UUID = _uuid.UUID("00000000-0000-7000-8000-000000000000")
SERVICE_ACTOR_TYPE = 2
PLATFORM_ADMIN_ROLE = "platform.admin"
TIER1_OPERATOR_ROLE = "operator"
PATIENT_SELF_ROLE = "patient.self"


def _row_to_dict(row: User) -> dict:
    return {
        "uuid": str(row.uuid),
        "tenant_uuid": str(row.tenant_uuid),
        "idp_id": row.idp_id,
        "display_code": row.display_code,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "email": row.email,
        "roles": list(row.roles or []),
        "tos_accepted": bool(row.tos_accepted),
    }


def get_user_or_404(user_id: str) -> dict:
    try:
        user_uuid = _uuid.UUID(str(user_id))
    except ValueError as exc:
        raise NotFound() from exc

    from src.db.engine import SessionLocal

    with SessionLocal() as db:
        row = db.get(User, user_uuid)
        if row is None:
            raise NotFound()
        return _row_to_dict(row)


def list_users(db, page: int, page_size: int, search: str) -> tuple[list[dict], int]:
    query = select(User).order_by(
        User.last_name.asc().nulls_last(),
        User.first_name.asc().nulls_last(),
    )
    if search:
        pattern = f"%{search}%"
        query = query.where(
            User.first_name.ilike(pattern)
            | User.last_name.ilike(pattern)
            | User.email.ilike(pattern)
            | User.idp_id.ilike(pattern)
            | User.display_code.ilike(pattern)
        )

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return [_row_to_dict(row) for row in rows], int(total or 0)


def update_user(db, actor_uuid: str, user_uuid: str, payload: dict, *, self_service: bool) -> dict:
    actor_id = _uuid.UUID(str(actor_uuid))
    target_id = _uuid.UUID(str(user_uuid))
    row = db.get(User, target_id)
    if row is None:
        raise NotFound()

    if self_service:
        for field in ("first_name", "last_name", "email"):
            if field in payload:
                value = (payload.get(field) or "").strip() or None
                setattr(row, field, value)
        if "tos_accepted" in payload:
            if payload.get("tos_accepted") is True:
                row.tos_accepted = True
    else:
        field_map = {
            "tenant_uuid": lambda v: _uuid.UUID(str(v)),
            "display_code": lambda v: (str(v).strip() or None) if v is not None else None,
            "first_name": lambda v: (str(v).strip() or None) if v is not None else None,
            "last_name": lambda v: (str(v).strip() or None) if v is not None else None,
            "email": lambda v: (str(v).strip() or None) if v is not None else None,
            "roles": lambda v: list(v or []),
        }
        for field, transform in field_map.items():
            if field in payload:
                setattr(row, field, transform(payload[field]))

    row.changed_by_uuid = actor_id
    row.changed_by_type = 1
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        display_code = row.display_code if row is not None else None
        raise ConflictError(_integrity_conflict_message(exc, display_code=display_code)) from exc
    db.refresh(row)
    return _row_to_dict(row)


def _actors(payload: dict) -> list[str]:
    roles = payload.get("actors")
    if roles is None:
        return []
    if not isinstance(roles, list):
        return []
    return [str(role).strip() for role in roles if str(role).strip()]


def _active_platform_admin_exists(db) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.roles.contains([PLATFORM_ADMIN_ROLE]))
    )
    return int(count or 0) > 0


def _bootstrap_platform_admin_roles(db, payload: dict) -> list[str]:
    if TIER1_OPERATOR_ROLE not in _actors(payload):
        return []
    if _active_platform_admin_exists(db):
        return []
    return [PLATFORM_ADMIN_ROLE]


def provision_user_identity(db, user_uuid: str, payload: dict) -> tuple[dict, bool]:
    target_id = _uuid.UUID(str(user_uuid))
    tenant_id = _uuid.UUID(str(payload["tenant_uuid"]))
    row = db.get(User, target_id)
    created = row is None

    values = {
        "tenant_uuid": tenant_id,
        "idp_id": str(payload["idp_id"]).strip(),
        "first_name": (str(payload["first_name"]).strip() or None)
        if payload.get("first_name") is not None
        else None,
        "last_name": (str(payload["last_name"]).strip() or None)
        if payload.get("last_name") is not None
        else None,
        "email": (str(payload["email"]).strip() or None)
        if payload.get("email") is not None
        else None,
    }

    if created:
        roles = _bootstrap_platform_admin_roles(db, payload)
        if roles:
            log_event("first_operator_bootstrapped")
        row = User(
            uuid=target_id,
            roles=roles,
            changed_by_uuid=SYSTEM_ACTOR_UUID,
            changed_by_type=SERVICE_ACTOR_TYPE,
            **values,
        )
        db.add(row)
    else:
        for field, value in values.items():
            setattr(row, field, value)
        row.changed_by_uuid = SYSTEM_ACTOR_UUID
        row.changed_by_type = SERVICE_ACTOR_TYPE

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(_integrity_conflict_message(exc, display_code=row.display_code)) from exc
    db.refresh(row)
    return _row_to_dict(row), created


def create_user(db, actor_uuid: str, payload: dict, *, assigner_actor_list: list[str]) -> tuple[dict, bool]:
    from src.domain.role_catalog import validate_roles_for_assigner_actors

    actor_id = _uuid.UUID(str(actor_uuid))
    tenant_id = _uuid.UUID(str(payload["tenant_uuid"]))

    roles = list(payload.get("roles") or [])
    from src.domain.role_catalog import actor_classes

    actors = [actor for actor in assigner_actor_list if actor in actor_classes()]
    clinician_only = actors == ["clinician"]
    if not roles:
        if clinician_only:
            roles = [PATIENT_SELF_ROLE]
        else:
            raise ValueError("roles is required")

    if clinician_only:
        if set(roles) != {PATIENT_SELF_ROLE}:
            raise ValueError("clinician enrollment may only assign patient.self to the new patient")
        if payload.get("uuid") or payload.get("idp_id"):
            raise ValueError("clinician enrollment may not specify uuid or idp_id")
    elif payload.get("uuid"):
        if set(roles) != {PATIENT_SELF_ROLE}:
            raise ValueError("stable uuid seeding may only assign patient.self")
    else:
        validate_roles_for_assigner_actors(roles, assigner_actor_list)

    first_name = str(payload["first_name"]).strip()
    last_name = str(payload["last_name"]).strip()
    email = str(payload["email"]).strip()
    if not first_name or not last_name or not email:
        raise ValueError("first_name, last_name, and email are required")

    display_code = payload.get("display_code")
    if display_code is not None:
        display_code = str(display_code).strip() or None

    if payload.get("uuid"):
        user_uuid = _uuid.UUID(str(payload["uuid"]))
    else:
        user_uuid = _uuid.uuid7()

    if payload.get("idp_id"):
        idp_id = str(payload["idp_id"]).strip()
        if not idp_id:
            raise ValueError("idp_id must not be empty")
    else:
        idp_id = f"enrolled_{user_uuid}"

    row = db.get(User, user_uuid)
    created = row is None
    if row is None:
        row = User(
            uuid=user_uuid,
            tenant_uuid=tenant_id,
            idp_id=idp_id,
            display_code=display_code,
            first_name=first_name,
            last_name=last_name,
            email=email,
            roles=roles,
            changed_by_uuid=actor_id,
            changed_by_type=1,
        )
        db.add(row)
    else:
        row.tenant_uuid = tenant_id
        row.idp_id = idp_id
        row.display_code = display_code
        row.first_name = first_name
        row.last_name = last_name
        row.email = email
        row.roles = roles
        row.changed_by_uuid = actor_id
        row.changed_by_type = 1

    if _display_code_in_use(db, tenant_id, display_code, exclude_uuid=None if created else user_uuid):
        raise ConflictError(_display_code_conflict_message(display_code))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(_integrity_conflict_message(exc, display_code=display_code)) from exc
    db.refresh(row)
    log_event("user_created", actor_uuid=actor_uuid, user_uuid=str(user_uuid), created=created)
    return _row_to_dict(row), created


def get_user_audits(db, user_uuid: str, page: int, page_size: int) -> tuple[list[dict], int]:
    target = _uuid.UUID(str(user_uuid))
    if db.get(User, target) is None:
        raise NotFound()

    history_table = UserHistory.__table__
    where_clause = history_table.c.uuid == target
    query = (
        select(history_table)
        .where(where_clause)
        .order_by(history_table.c.changed_at.desc())
    )

    total = db.scalar(
        select(func.count()).select_from(
            select(history_table).where(where_clause).subquery()
        )
    )
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).mappings().all()

    items = []
    for row in rows:
        items.append({
            "history_uuid": str(row["history_uuid"]) if row["history_uuid"] else None,
            "uuid": str(row["uuid"]),
            "tenant_uuid": str(row["tenant_uuid"]),
            "idp_id": row["idp_id"],
            "display_code": row["display_code"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "email": row["email"],
            "roles": list(row["roles"] or []),
            "changed_at": row["changed_at"].isoformat() if row["changed_at"] else None,
            "changed_by_uuid": str(row["changed_by_uuid"]),
            "changed_by_type": row["changed_by_type"],
            "change_type": row["change_type"],
        })
    return items, int(total or 0)
