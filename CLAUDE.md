# CLAUDE.md — guide for LLM coding agents

This repo is **auto-ticket-service**: a FastAPI web service that raises a GitHub issue
from any UI/backend, a background poller that auto-discovers new issues, and a Streamlit
demo showing the reusable floating 🐞 bug icon. Postgres stores every ticket.

## Run it

```bash
cp .env.example .env          # MOCK_GITHUB=true by default — no credentials
docker compose up --build     # UI :8501 · API :8000/docs · Postgres
cd service && MOCK_GITHUB=true python -m pytest -q   # unit tests, no DB/network
```

Mock mode (`MOCK_GITHUB=true` or no `GITHUB_TOKEN`) simulates GitHub so everything runs
offline. Set `MOCK_GITHUB=false` + `GITHUB_TOKEN` + `GITHUB_REPO` for real issues.

## Where things live

- `service/app/routes.py` — the public HTTP contract. Change this only to add/alter endpoints.
- `service/app/tickets.py` — create-ticket + sync-from-GitHub logic (transport-independent). Most business-logic changes go here.
- `service/app/github.py` — the only code that calls github.com. Has a mock branch (`settings.use_mock`) — keep both branches in sync when you change behaviour.
- `service/app/poller.py` — the auto-check loop; updates `poller.state` for `/health`.
- `service/app/models.py` / `schemas.py` — DB row / API contract. Changing a schema is a public API change.
- `ui/app.py` — Streamlit demo; the floating icon is a keyed button restyled via the `.st-key-bug_fab` CSS.
- `docs/` — API.md, INTEGRATION.md, ARCHITECTURE.md. **Update these when you change the API.**

## Conventions

- GitHub calls are **best-effort** — never let issue creation raise into the request path; store the ticket regardless. Preserve this.
- Keep the mock path working: a change that only works with a real token breaks the default `docker compose up`.
- New endpoints: register static paths (`/tickets/new`) before parameterised ones (`/tickets/{id}`) — FastAPI matches in registration order.
- Settings are env-driven via `config.py`; don't hardcode hosts, tokens, or repos.
- Treat `GITHUB_TOKEN` as a secret: never print it or write it into committed files.

## When integrating the icon into another app

Follow `docs/INTEGRATION.md` for the target framework. Identify the frontend framework
first and confirm it before writing UI code. Point the client at the service via an
`API_URL`/`TICKET_API` env var — never a hardcoded host.
