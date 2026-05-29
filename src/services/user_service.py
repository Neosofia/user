from __future__ import annotations

import uuid as _uuid

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound

from src.models.user import User


class ConflictError(Exception):
    pass


def _row_to_dict(row: User) -> dict:
    return {
        "uuid": str(row.uuid),
        "tenant_uuid": str(row.tenant_uuid),
        "idp_id": row.idp_id,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "email": row.email,
        "platform_roles": list(row.platform_roles or []),
    }


def get_user_or_404(user_id: str) -> dict:
    try:
        user_uuid = _uuid.UUID(str(user_id))
    except ValueError as exc:
        raise NotFound() from exc

    from src.db.engine import SessionLocal

    with SessionLocal() as db:
        row = db.get(User, user_uuid)
        if row is None or row.change_type == 3:
            raise NotFound()
        return _row_to_dict(row)


def list_users(db, page: int, page_size: int, search: str) -> tuple[list[dict], int]:
    query = (
        select(User)
        .where(User.change_type != 3)
        .order_by(User.last_name.asc().nulls_last(), User.first_name.asc().nulls_last())
    )
    if search:
        pattern = f"%{search}%"
        query = query.where(
            User.first_name.ilike(pattern)
            | User.last_name.ilike(pattern)
            | User.email.ilike(pattern)
            | User.idp_id.ilike(pattern)
        )

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return [_row_to_dict(row) for row in rows], int(total or 0)


def update_user(db, actor_uuid: str, user_uuid: str, payload: dict, *, self_service: bool) -> dict:
    actor_id = _uuid.UUID(str(actor_uuid))
    target_id = _uuid.UUID(str(user_uuid))
    row = db.get(User, target_id)
    if row is None or row.change_type == 3:
        raise NotFound()

    if self_service:
        for field in ("first_name", "last_name", "email"):
            if field in payload:
                value = (payload.get(field) or "").strip() or None
                setattr(row, field, value)
    else:
        field_map = {
            "tenant_uuid": lambda v: _uuid.UUID(str(v)),
            "first_name": lambda v: (str(v).strip() or None) if v is not None else None,
            "last_name": lambda v: (str(v).strip() or None) if v is not None else None,
            "email": lambda v: (str(v).strip() or None) if v is not None else None,
            "platform_roles": lambda v: list(v or []),
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
        raise ConflictError("user update conflict") from exc
    db.refresh(row)
    return _row_to_dict(row)


def get_user_audits(db, user_uuid: str, page: int, page_size: int) -> tuple[list[dict], int]:
    from sqlalchemy import text

    target = _uuid.UUID(str(user_uuid))
    exists = db.get(User, target)
    if exists is None:
        raise NotFound()

    count_sql = text(
        """
        SELECT count(*) FROM users_audit
        WHERE uuid = :user_uuid
        """
    )
    total = db.scalar(count_sql, {"user_uuid": target})

    rows = db.execute(
        text(
            """
            SELECT history_uuid, uuid, tenant_uuid, idp_id, first_name, last_name, email,
                   platform_roles, changed_at, changed_by_uuid, changed_by_type, change_type
            FROM users_audit
            WHERE uuid = :user_uuid
            ORDER BY changed_at DESC
            OFFSET :offset LIMIT :limit
            """
        ),
        {"user_uuid": target, "offset": (page - 1) * page_size, "limit": page_size},
    ).mappings().all()

    items = []
    for row in rows:
        items.append({
            "history_uuid": str(row["history_uuid"]) if row["history_uuid"] else None,
            "uuid": str(row["uuid"]),
            "tenant_uuid": str(row["tenant_uuid"]),
            "idp_id": row["idp_id"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "email": row["email"],
            "platform_roles": list(row["platform_roles"] or []),
            "changed_at": row["changed_at"].isoformat() if row["changed_at"] else None,
            "changed_by_uuid": str(row["changed_by_uuid"]),
            "changed_by_type": row["changed_by_type"],
            "change_type": row["change_type"],
        })
    return items, int(total or 0)
