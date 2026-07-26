"""Ticket business logic: turn an incoming request into a GitHub issue + DB row.

Kept separate from the HTTP layer so the poller and any future transport (a
queue consumer, a gRPC endpoint) can reuse the exact same creation path.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import github
from app.github import CATEGORY_COLORS
from app.models import Ticket
from app.schemas import TicketCreate

logger = logging.getLogger(__name__)


def _build_issue_body(payload: TicketCreate) -> str:
    """Render the issue body Markdown — mirrors the format Claude Code triages."""
    cat_label = {"bug": "🐛 bug", "idea": "💡 idea", "improvement": "🔧 improvement"}.get(
        payload.category, payload.category
    )
    lines = [
        f"**Ticket raised from `{payload.source}`.**",
        "",
        f"- **Category:** {cat_label}",
        f"- **Source:** {payload.source}",
        f"- **Reporter:** {payload.reporter or '(anonymous)'}",
        f"- **Submitted:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    for key, value in (payload.meta or {}).items():
        lines.append(f"- **{key}:** {value}")
    lines += ["", "### Description", payload.body or "(no description)"]
    if payload.screenshot_url:
        # GitHub renders http(s) images but NOT data: URIs, and a base64 data URI
        # would also blow past the ~65 KB issue-body limit. So embed real URLs and
        # just note the attachment for data URIs (viewable in the service UI / API).
        if payload.screenshot_url.startswith(("http://", "https://")):
            lines += ["", "### Screenshot", f"![screenshot]({payload.screenshot_url})"]
        else:
            lines += ["", "_📎 Screenshot attached (captured in-app; view it via the service UI/API)._"]
    lines += [
        "",
        "---",
        "_Auto-created by auto-ticket-service. Claude Code: triage on next session._",
    ]
    return "\n".join(lines)


async def create_ticket(session: AsyncSession, payload: TicketCreate) -> Ticket:
    """Open a GitHub issue for `payload` and persist the resulting ticket.

    Best-effort on GitHub: if the issue call fails the ticket is still stored
    (github_number/url null) so nothing a user submitted is ever dropped.
    """
    labels = [(payload.category, CATEGORY_COLORS.get(payload.category, "ededed")), ("auto-ticket", "0e8a16")]
    labels += [(l, "ededed") for l in payload.labels]

    body = _build_issue_body(payload)
    result = await github.create_issue(payload.title, body, labels)

    ticket = Ticket(
        title=payload.title,
        body=payload.body,
        category=payload.category,
        source=payload.source,
        reporter=payload.reporter,
        screenshot_url=payload.screenshot_url,
        meta=payload.meta or {},
        github_number=result["number"] if result else None,
        github_url=result["url"] if result else None,
        status=result["state"] if result else "open",
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    logger.info("Ticket %s created (issue #%s)", ticket.id, ticket.github_number)
    return ticket


async def sync_from_github(session: AsyncSession) -> int:
    """Pull open issues from GitHub and insert any not already stored.

    Returns the number of NEW tickets discovered. This is what powers the
    "auto-check for new issues" feature — a UI polls /tickets and sees issues
    that were opened on GitHub directly, not just ones it raised itself.
    """
    issues = await github.list_open_issues()
    if not issues:
        return 0

    existing = set(
        (await session.execute(select(Ticket.github_number).where(Ticket.github_number.isnot(None)))).scalars().all()
    )

    new_count = 0
    for issue in issues:
        if issue["number"] in existing:
            continue
        labels = issue.get("labels", [])
        category = next((c for c in ("bug", "idea", "improvement") if c in labels), "bug")
        session.add(Ticket(
            title=issue["title"],
            body=issue.get("body", ""),
            category=category,
            source="github-poller",
            github_number=issue["number"],
            github_url=issue["url"],
            status=issue["state"],
            meta={"labels": labels},
        ))
        new_count += 1

    if new_count:
        await session.commit()
        logger.info("Poller discovered %d new issue(s)", new_count)
    return new_count
