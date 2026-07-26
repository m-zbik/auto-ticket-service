"""Unit tests for the credential-free core (mock GitHub client + body builder).

    cd service && MOCK_GITHUB=true python -m pytest

These run without a database or network. The DB-backed create/list paths are
exercised end-to-end by `docker compose up` + the smoke steps in the README.
"""

import os

os.environ.setdefault("MOCK_GITHUB", "true")

import asyncio

from app import github
from app.schemas import TicketCreate
from app.tickets import _build_issue_body


def test_mock_create_issue_returns_number_and_url():
    res = asyncio.run(github.create_issue("Title", "body", [("bug", "d73a4a")]))
    assert res is not None
    assert isinstance(res["number"], int)
    assert res["url"].endswith(f"/issues/{res['number']}")
    assert res["state"] == "open"


def test_mock_list_reflects_created():
    async def scenario():
        before = len(await github.list_open_issues())
        await github.create_issue("Another", "b", [("idea", "a2eeef")])
        after = await github.list_open_issues()
        return before, after

    before, after = asyncio.run(scenario())
    assert len(after) == before + 1
    assert all("number" in i and "url" in i for i in after)


def test_body_includes_meta_description_and_screenshot():
    payload = TicketCreate(
        title="T", body="steps here", category="bug", source="web-portal",
        reporter="a@b.com", meta={"route": "/dashboard"},
        screenshot_url="https://example.com/s.png",
    )
    body = _build_issue_body(payload)
    assert "steps here" in body
    assert "route" in body and "/dashboard" in body
    assert "![screenshot](https://example.com/s.png)" in body
    assert "auto-ticket-service" in body


def test_body_handles_empty_optional_fields():
    body = _build_issue_body(TicketCreate(title="Only title"))
    assert "(no description)" in body
    assert "Screenshot" not in body
