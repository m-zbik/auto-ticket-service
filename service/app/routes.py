"""HTTP API. This is the contract any UI or backend integrates against.

    POST   /tickets            raise a ticket (JSON)           -> TicketOut
    POST   /tickets/multipart  raise a ticket with a file      -> TicketOut
    GET    /tickets            list stored tickets             -> TicketList
    GET    /tickets/{id}       fetch one                       -> TicketOut
    GET    /tickets/new        issues found since a timestamp  -> TicketList
    POST   /tickets/sync       force a poll now                -> {new: N}
    GET    /health             liveness + mode + poller state  -> HealthOut
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import poller
from app.config import get_settings
from app.database import get_session
from app.models import Ticket
from app.schemas import HealthOut, TicketCreate, TicketList, TicketOut
from app.tickets import create_ticket, sync_from_github

router = APIRouter()


@router.get("/health", response_model=HealthOut, tags=["meta"])
async def health(session: AsyncSession = Depends(get_session)) -> HealthOut:
    settings = get_settings()
    count = (await session.execute(select(func.count(Ticket.id)))).scalar_one()
    return HealthOut(
        status="ok",
        service=settings.service_name,
        mode="mock" if settings.use_mock else "github",
        repo=settings.github_repo,
        poller_enabled=settings.poll_enabled,
        last_poll_at=poller.state.last_poll_at,
        ticket_count=count,
    )


@router.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED, tags=["tickets"])
async def post_ticket(payload: TicketCreate, session: AsyncSession = Depends(get_session)) -> TicketOut:
    """Raise a ticket. Opens a GitHub issue and stores the record. This is the
    endpoint a bug icon in any UI (or any backend) calls."""
    ticket = await create_ticket(session, payload)
    return TicketOut(**ticket.to_dict())


@router.post("/tickets/multipart", response_model=TicketOut, status_code=status.HTTP_201_CREATED, tags=["tickets"])
async def post_ticket_multipart(
    title: str = Form(...),
    body: str = Form(""),
    category: str = Form("bug"),
    source: str = Form("api"),
    reporter: str = Form(""),
    meta: str = Form("{}"),
    screenshot: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
) -> TicketOut:
    """Same as POST /tickets but accepts a binary screenshot upload (multipart) —
    convenient for a mobile app or a browser form. The image is stored inline as a
    data: URI so the demo has zero external image-hosting dependency; a production
    build would push it to object storage / the repo and embed that URL instead."""
    try:
        meta_dict = json.loads(meta) if meta else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="meta must be valid JSON")

    screenshot_url = None
    if screenshot is not None:
        import base64
        raw = await screenshot.read()
        if raw:
            mime = screenshot.content_type or "image/png"
            screenshot_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"

    payload = TicketCreate(
        title=title, body=body, category=category, source=source,
        reporter=reporter or None, screenshot_url=screenshot_url, meta=meta_dict,
    )
    ticket = await create_ticket(session, payload)
    return TicketOut(**ticket.to_dict())


@router.get("/tickets", response_model=TicketList, tags=["tickets"])
async def list_tickets(
    limit: int = Query(50, ge=1, le=200),
    category: str | None = Query(None),
    source: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> TicketList:
    stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)
    if category:
        stmt = stmt.where(Ticket.category == category)
    if source:
        stmt = stmt.where(Ticket.source == source)
    rows = (await session.execute(stmt)).scalars().all()
    return TicketList(count=len(rows), tickets=[TicketOut(**r.to_dict()) for r in rows])


@router.get("/tickets/new", response_model=TicketList, tags=["tickets"])
async def new_tickets(
    since: datetime | None = Query(None, description="ISO-8601; return tickets created after this"),
    session: AsyncSession = Depends(get_session),
) -> TicketList:
    """Tickets discovered/created since `since` — the polling feed a UI hits to
    show a badge like '3 new issues'. Omit `since` to get the most recent."""
    stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(50)
    if since is not None:
        stmt = select(Ticket).where(Ticket.created_at > since).order_by(Ticket.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return TicketList(count=len(rows), tickets=[TicketOut(**r.to_dict()) for r in rows])


@router.post("/tickets/sync", tags=["tickets"])
async def force_sync(session: AsyncSession = Depends(get_session)) -> dict:
    """Trigger an immediate GitHub→DB sync instead of waiting for the poll interval."""
    new = await sync_from_github(session)
    return {"new": new, "last_poll_at": poller.state.last_poll_at}


@router.get("/tickets/{ticket_id}", response_model=TicketOut, tags=["tickets"])
async def get_ticket(ticket_id: str, session: AsyncSession = Depends(get_session)) -> TicketOut:
    row = await session.get(Ticket, ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketOut(**row.to_dict())
