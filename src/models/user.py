from __future__ import annotations

import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.engine import Base
from src.models.audit_mixin import AuditColumnsMixin, HistoryColumnsMixin


class User(Base, AuditColumnsMixin):
    __tablename__ = "users"

    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="Same as users.uuid in Authentication (JWT sub)",
    )
    tenant_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    idp_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-facing shorthand within the tenant (e.g. DET-4035)",
    )
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")


class UserHistory(Base, HistoryColumnsMixin):
    __tablename__ = "users_history"

    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    idp_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
