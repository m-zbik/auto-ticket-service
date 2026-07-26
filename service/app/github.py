"""GitHub REST client for issues — the one place that talks to github.com.

Distilled from a production feedback→issue integration. Two public coroutines:

    create_issue(...)  -> open an issue, ensuring labels exist first (idempotent)
    list_open_issues() -> read open issues (used by the poller to find new ones)

Both are best-effort and never raise into the caller. When settings.use_mock is
true (no token, or MOCK_GITHUB=true) they simulate GitHub with an in-process
counter so the full stack runs with zero credentials.
"""

from __future__ import annotations

import itertools
import logging
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_API = "https://api.github.com"

# Default colours for the well-known feedback categories (hex, no '#').
CATEGORY_COLORS = {"bug": "d73a4a", "idea": "a2eeef", "improvement": "fbca04"}

# --- mock state -------------------------------------------------------------
# A monotonic counter fakes GitHub's issue numbering so mock URLs look real and
# the DB's unique-number constraint behaves the same as against real GitHub.
_mock_counter = itertools.count(1001)
_mock_issues: list[dict[str, Any]] = []


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _ensure_label(
    client: httpx.AsyncClient, repo: str, headers: dict[str, str], name: str, color: str,
) -> None:
    """Create a label if missing. 422 (already exists) is fine; failures are non-fatal."""
    try:
        await client.post(
            f"{_API}/repos/{repo}/labels",
            json={"name": name, "color": color}, headers=headers,
        )
    except Exception as e:  # pragma: no cover - network
        logger.debug("ensure label %s failed: %s", name, e)


async def create_issue(
    title: str,
    body: str,
    labels: list[tuple[str, str]],
) -> Optional[dict[str, Any]]:
    """Open a GitHub issue. Returns {"number", "url", "state"} or None on failure.

    `labels` is a list of (name, colour) pairs; each is ensured to exist first so
    label filtering works. If a label still won't resolve (422) the issue is
    retried without labels rather than lost.
    """
    settings = get_settings()
    repo = settings.github_repo
    label_names = [n for n, _ in labels]

    if settings.use_mock:
        number = next(_mock_counter)
        issue = {
            "number": number,
            "url": f"https://github.com/{repo}/issues/{number}",
            "state": "open",
            "title": title,
            "labels": label_names,
        }
        _mock_issues.append(issue)
        logger.info("[mock] created issue #%s: %s", number, title)
        return {"number": number, "url": issue["url"], "state": "open"}

    headers = _headers(settings.github_token)
    async with httpx.AsyncClient(timeout=15) as client:
        for name, color in labels:
            await _ensure_label(client, repo, headers, name, color)

        api = f"{_API}/repos/{repo}/issues"
        payload: dict[str, Any] = {"title": title, "body": body, "labels": label_names}
        resp = await client.post(api, json=payload, headers=headers)
        if resp.status_code == 422:  # a label didn't resolve — retry without labels
            payload.pop("labels", None)
            resp = await client.post(api, json=payload, headers=headers)
        if resp.status_code in (200, 201):
            data = resp.json()
            logger.info("Created GitHub issue: %s", data.get("html_url"))
            return {
                "number": data.get("number"),
                "url": data.get("html_url"),
                "state": data.get("state", "open"),
            }
        logger.warning("GitHub issue creation failed (%s): %s", resp.status_code, resp.text[:200])
        return None


async def list_open_issues(per_page: int = 50) -> list[dict[str, Any]]:
    """List open issues (excluding PRs). Returns a list of normalized dicts.

    Used by the poller to discover issues opened directly on GitHub (not via this
    service) so a UI can show a "new issues" feed.
    """
    settings = get_settings()
    repo = settings.github_repo

    if settings.use_mock:
        return [
            {
                "number": i["number"], "title": i["title"],
                "url": i["url"], "state": i["state"],
                "labels": i.get("labels", []), "body": "",
            }
            for i in _mock_issues if i["state"] == "open"
        ]

    headers = _headers(settings.github_token)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{_API}/repos/{repo}/issues",
                params={"state": "open", "per_page": per_page},
                headers=headers,
            )
        if resp.status_code != 200:
            logger.warning("GitHub list issues failed (%s): %s", resp.status_code, resp.text[:200])
            return []
        out = []
        for issue in resp.json():
            if issue.get("pull_request"):
                continue  # the issues endpoint also returns PRs
            out.append({
                "number": issue["number"],
                "title": issue.get("title", ""),
                "url": issue.get("html_url"),
                "state": issue.get("state", "open"),
                "labels": [l["name"] for l in issue.get("labels", [])],
                "body": issue.get("body") or "",
            })
        return out
    except Exception as e:  # pragma: no cover - network
        logger.warning("GitHub list issues error: %s", e)
        return []
