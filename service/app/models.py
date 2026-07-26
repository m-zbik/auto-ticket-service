"""Persistence model: one row per ticket.

A ticket is our record of a GitHub issue. It's created in two ways:
  1. A UI/backend POSTs to /tickets  → we open a GitHub issue and store it here.
  2. The background poller finds an issue opened directly on GitHub → stored here
     with source="github-poller" so a UI can surface "new issues" it didn't raise.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    __tablename__ = "tickets"
    # A GitHub issue number is unique per repo — guards against the poller and the
    # create path inserting the same issue twice.
    __table_args__ = (UniqueConstraint("github_number", name="uq_ticket_github_number"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50), default="bug")     # bug | idea | improvement
    source: Mapped[str] = mapped_column(String(100), default="api")      # which UI/app raised it
    reporter: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # GitHub linkage (null while a ticket is pending / in pure-mock offline runs)
    github_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")      # open | closed

    screenshot_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "title": self.title,
            "body": self.body,
            "category": self.category,
            "source": self.source,
            "reporter": self.reporter,
            "github_number": self.github_number,
            "github_url": self.github_url,
            "status": self.status,
            "screenshot_url": self.screenshot_url,
            "meta": self.meta or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
