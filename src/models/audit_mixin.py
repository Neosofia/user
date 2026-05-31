from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, SmallInteger, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class AuditColumnsMixin:
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    changed_by_type: Mapped[int] = mapped_column(SmallInteger)
    change_type: Mapped[int] = mapped_column(SmallInteger, server_default="1")


class HistoryColumnsMixin(AuditColumnsMixin):
    history_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid7,
    )
