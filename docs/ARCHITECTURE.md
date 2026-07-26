# Architecture

## Goal

Make "report a bug" a **one-HTTP-call capability** that any UI or backend can adopt in
minutes, and keep a **local record** of every issue so a UI never has to talk to GitHub
directly (rate limits, auth, latency). The service is the seam between your apps and
GitHub Issues.

## Components

| Component | Tech | Responsibility |
|-----------|------|----------------|
| **API service** | FastAPI (async) | Public HTTP contract; opens issues; reads/writes tickets |
| **GitHub client** | httpx | The only code that calls github.com; has a mock |
| **Poller** | asyncio task | Periodically syncs open issues GitHub → Postgres |
| **Database** | Postgres | Source of truth the UI reads; enables de-dup + the "new issues" feed |
| **Demo UI** | Streamlit | Mock host app proving the floating 🐞 icon end-to-end |

```
        POST /tickets                     REST (create issue)
 UI ───────────────────▶  FastAPI  ─────────────────────────▶  GitHub Issues
  ▲   GET /tickets/new       │  ▲                                     │
  │                          ▼  │  poll (list issues, every 60s)      │
  └──────────────────────  Postgres  ◀────────── Poller ◀─────────────┘
```

### Request path — `POST /tickets`

`routes.post_ticket` → `tickets.create_ticket`:

1. Build labels `[(category, colour), ("auto-ticket", …), …extra]`.
2. Render the issue body Markdown (`_build_issue_body`) — category, source, reporter, `meta`, description, screenshot.
3. `github.create_issue(...)` — ensures each label exists (idempotent; 422 = already there), POSTs the issue, retries without labels if a label still won't resolve.
4. Persist a `Ticket` row with the returned issue number/URL.

Best-effort discipline: a GitHub failure never raises to the caller. The ticket is
stored regardless (with null GitHub fields) so no user submission is lost — the same
principle as the source `github_issues.py` it's distilled from.

### Poller path — auto-check for new issues

`poller._loop` runs every `POLL_INTERVAL_SECONDS`:

1. `github.list_open_issues()` — open issues, PRs filtered out.
2. `tickets.sync_from_github` — inserts any issue whose number isn't already a `Ticket`.
3. Updates `poller.state` (`last_poll_at`, counts), surfaced via `/health`.

This lets a UI show issues opened **directly on GitHub**, not only ones it raised.
`POST /tickets/sync` forces an immediate pass; `GET /tickets/new?since=` is the feed.

## Key design decisions

**Mock mode by default.** `settings.use_mock` is true when `MOCK_GITHUB=true` *or* no
`GITHUB_TOKEN` is set. The GitHub client then simulates issue creation with a monotonic
counter and an in-process list. Result: `docker compose up` works with zero credentials,
so anyone can evaluate the full flow (icon → API → DB → feed) offline, then flip one flag.

**Postgres as the UI's source of truth.** Reading tickets from our DB — not GitHub —
keeps the UI fast, avoids leaking a GitHub token to browsers, survives GitHub outages,
and gives the poller a place to de-dup against (`uq_ticket_github_number`).

**Business logic split from transport.** `tickets.py` (create/sync) is independent of
FastAPI, so the poller, a future queue consumer, or tests reuse the exact same path.

**Screenshots as `data:` URIs (reference build).** The multipart endpoint inlines the
image so the demo has no object-storage dependency. The original production integration
instead committed screenshots to a dedicated repo branch so GitHub hosts them inline and
permanently — see [Hardening](#hardening-for-production).

## Data model

`tickets` — one row per issue we created or discovered:

| Column | Notes |
|--------|-------|
| `id` (uuid) | Service-side id |
| `title`, `body`, `category` | `category` ∈ bug/idea/improvement |
| `source`, `reporter` | Which app raised it; who reported |
| `github_number` (unique), `github_url`, `status` | GitHub linkage; null until/if the issue call succeeds |
| `screenshot_url`, `meta` (jsonb) | Optional image; arbitrary context |
| `created_at`, `synced_at` | Timestamps |

`create_all` on startup is fine for a demo; a production build swaps in Alembic migrations.

## Configuration (env)

| Var | Default | Meaning |
|-----|---------|---------|
| `MOCK_GITHUB` | `true` (compose) | Simulate GitHub |
| `GITHUB_TOKEN` | — | PAT, Issues: read & write |
| `GITHUB_REPO` | `owner/repo` | Target repo |
| `DATABASE_URL` | compose value | asyncpg DSN |
| `POLL_ENABLED` | `true` | Run the background poller |
| `POLL_INTERVAL_SECONDS` | `60` | Sync cadence |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

## Failure modes

| Situation | Behaviour |
|-----------|-----------|
| GitHub down / bad token | Ticket still stored; `github_url` null; warning logged |
| DB down at startup | `pool_pre_ping` + healthcheck; compose waits for `db` healthy first |
| Label doesn't exist | Auto-created; if it still 422s, issue retried without labels |
| Poller iteration errors | Caught; loop continues next interval |
| Screenshot capture failed (client) | Send text-only rather than dropping the report |

## Hardening for production

- **Auth:** the create endpoint is open by default (fine for internal tools behind a
  gateway). Add an API key / JWT check and lock `CORS_ORIGINS` to your UI origin.
- **Secrets:** inject `GITHUB_TOKEN` from your platform's secret store, not a committed `.env`.
- **Migrations:** replace `create_all` with Alembic.
- **Screenshots:** push to object storage (S3/GCS) or commit to a repo branch so images
  are hosted independently of this service, and store that URL.
- **Rate limits & de-dup:** add a fingerprint (title + source hash) to comment on an
  existing open issue instead of opening duplicates — the source `create_test_failure_issue`
  shows this pattern.
- **Observability:** ship logs/metrics; alert if `last_poll_at` goes stale.
- **Scale:** run one poller replica (or add a leader lock) so N API replicas don't each poll.
