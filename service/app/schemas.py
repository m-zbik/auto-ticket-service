"""Request/response contracts. This is the public API any UI or backend codes against."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["bug", "idea", "improvement"]


class TicketCreate(BaseModel):
    """Payload a UI/backend sends to raise a ticket.

    Only `title` is required. `screenshot_url` is any publicly reachable image URL
    (or a data: URI); the service embeds it in the GitHub issue as-is. For binary
    upload use the multipart variant of the endpoint instead.
    """

    title: str = Field(..., min_length=1, max_length=500, examples=["Login button does nothing"])
    body: str = Field("", description="Free-text description / steps to reproduce")
    category: Category = "bug"
    source: str = Field("api", description="Which app/UI/screen raised this", examples=["web-portal"])
    reporter: Optional[str] = Field(None, examples=["jane@example.com"])
    screenshot_url: Optional[str] = None
    labels: list[str] = Field(default_factory=list, description="Extra GitHub labels")
    meta: dict[str, Any] = Field(default_factory=dict, description="Arbitrary context (route, app version, device…)")


class TicketOut(BaseModel):
    id: str
    title: str
    body: str
    category: str
    source: str
    reporter: Optional[str]
    github_number: Optional[int]
    github_url: Optional[str]
    status: str
    screenshot_url: Optional[str]
    meta: dict[str, Any]
    created_at: Optional[str]


class TicketList(BaseModel):
    count: int
    tickets: list[TicketOut]


class HealthOut(BaseModel):
    status: str
    service: str
    mode: Literal["github", "mock"]
    repo: str
    poller_enabled: bool
    last_poll_at: Optional[datetime]
    ticket_count: int
