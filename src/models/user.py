from __future__ import annotations

import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.engine import Base
from src.models.audit_mixin import AuditColumnsMixin


class User(Base, AuditColumnsMixin):
    __tablename__ = "users"

    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="Same as users.uuid in Authentication (JWT sub)",
    )
    tenant_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    idp_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
