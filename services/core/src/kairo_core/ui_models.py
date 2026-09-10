from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import uuid_pk


class WorkspaceLayout(Base):
    __tablename__ = "workspace_layouts"

    id: Mapped[uuid.UUID] = uuid_pk()
    subject_ref: Mapped[str] = mapped_column(String(320), nullable=False)
    workspace_key: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    layout_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("subject_ref", "workspace_key", name="uq_workspace_layout_subject_key"),
    )
