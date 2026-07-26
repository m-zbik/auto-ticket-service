# API Reference

Base URL (local): `http://localhost:8000`. Interactive docs: `GET /docs` (Swagger) and `/redoc`.

All endpoints are JSON unless noted. No auth by default — see [ARCHITECTURE.md](ARCHITECTURE.md#hardening-for-production) before exposing publicly.

---

## `GET /health`

Liveness, current mode, and poller state. Use it to confirm whether the service is
talking to real GitHub or running mocked.

```json
{
  "status": "ok",
  "service": "auto-ticket-service",
  "mode": "mock",                       // "mock" | "github"
  "repo": "owner/repo",
  "poller_enabled": true,
  "last_poll_at": "2026-07-26T18:40:11Z",
  "ticket_count": 12
}
```

---

## `POST /tickets`

Raise a ticket. Opens a GitHub issue and stores the record. **This is the endpoint a
bug icon calls.**

**Request body**

| Field            | Type     | Required | Notes |
|------------------|----------|----------|-------|
| `title`          | string   | ✅       | Issue title (1–500 chars) |
| `body`           | string   |          | Description / steps to reproduce |
| `category`       | enum     |          | `bug` \| `idea` \| `improvement` (default `bug`) |
| `source`         | string   |          | Which app/UI/screen raised it, e.g. `web-portal` |
| `reporter`       | string   |          | Email/username of the reporter |
| `screenshot_url` | string   |          | Any reachable image URL or `data:` URI; embedded in the issue |
| `labels`         | string[] |          | Extra GitHub labels to add |
| `meta`           | object   |          | Arbitrary context (route, app version, device…) rendered into the issue |

```bash
curl -X POST http://localhost:8000/tickets \
  -H 'Content-Type: application/json' \
  -d '{
        "title": "Login button does nothing",
        "body": "Tapping Login on the sign-in screen has no effect.",
        "category": "bug",
        "source": "web-portal",
        "reporter": "jane@example.com",
        "meta": {"route": "/login", "app_version": "2.3.1"}
      }'
```

**Response `201`**

```json
{
  "id": "0b1e…-uuid",
  "title": "Login button does nothing",
  "body": "Tapping Login…",
  "category": "bug",
  "source": "web-portal",
  "reporter": "jane@example.com",
  "github_number": 1001,
  "github_url": "https://github.com/owner/repo/issues/1001",
  "status": "open",
  "screenshot_url": null,
  "meta": {"route": "/login", "app_version": "2.3.1"},
  "created_at": "2026-07-26T18:41:02Z"
}
```

> If GitHub is unreachable the ticket is still stored (with `github_number`/`github_url`
> null) so nothing a user submitted is lost.

---

## `POST /tickets/multipart`

Same as `POST /tickets` but `multipart/form-data`, accepting a binary **screenshot**
upload — convenient for browser forms and mobile apps. Fields: `title`, `body`,
`category`, `source`, `reporter`, `meta` (JSON string), and file field `screenshot`.

```bash
curl -X POST http://localhost:8000/tickets/multipart \
  -F 'title=Map tiles missing' \
  -F 'category=bug' \
  -F 'source=ios-app' \
  -F 'meta={"screen":"MapView"}' \
  -F 'screenshot=@/path/to/shot.png'
```

The image is embedded in the issue (as a `data:` URI in this reference build). Returns
the same `TicketOut` shape as above.

---

## `GET /tickets`

List stored tickets, newest first.

**Query params:** `limit` (1–200, default 50), `category`, `source`.

```bash
curl 'http://localhost:8000/tickets?category=bug&limit=20'
```

```json
{ "count": 2, "tickets": [ { /* TicketOut */ }, { /* TicketOut */ } ] }
```

---

## `GET /tickets/new`

The **auto-check for new issues** feed: tickets created/discovered since a timestamp.
A UI stores the last time it checked and passes it back to show a "3 new issues" badge.

**Query params:** `since` (ISO-8601). Omit to get the 50 most recent.

```bash
curl 'http://localhost:8000/tickets/new?since=2026-07-26T18:00:00Z'
```

Same shape as `GET /tickets`.

---

## `POST /tickets/sync`

Force an immediate GitHub → DB sync instead of waiting for the poll interval. Useful
right after creating issues on GitHub, or from a "Refresh" button.

```bash
curl -X POST http://localhost:8000/tickets/sync
# {"new": 3, "last_poll_at": "2026-07-26T18:42:00Z"}
```

---

## `GET /tickets/{id}`

Fetch a single ticket by its service UUID. `404` if unknown.

---

## Errors

| Status | Meaning |
|--------|---------|
| `201`  | Ticket created |
| `404`  | Ticket not found |
| `422`  | Validation error (missing `title`, bad `meta` JSON, invalid `category`) |

GitHub failures are **not** surfaced as errors — the ticket is stored regardless and
`github_url` is null. Check `/health` `mode` and the service logs if issues aren't
appearing on GitHub.
