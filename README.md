# Auto-Ticket Service 🐞

A tiny, self-contained **web service that turns a bug report into a GitHub issue** —
callable from *any* UI and *any* backend with a single HTTP request. It ships with:

- a **FastAPI service** (`/service`) that opens GitHub issues and stores every ticket in Postgres,
- a **background poller** that auto-discovers issues opened directly on GitHub ("new issues" feed),
- a **Streamlit demo UI** (`/ui`) showing the reusable **floating 🐞 bug icon** that **captures a screenshot of the screen and lets you draw on it** (the same idea as the iOS ladybug + PencilKit flow) — no file upload,
- **Docker + docker-compose** wiring all of it — service, UI, and database — into `docker compose up`.

It runs **out of the box with no GitHub credentials** (mock mode), so you can demo the whole flow offline, then flip one flag to hit a real repo.

---

## 🤖 Set this up with Claude Code (copy-paste)

> **New developer?** Paste one of the prompts below into [Claude Code](https://claude.com/claude-code). Pick by what you want:
>
> | Prompt | Use it when you want to… |
> |--------|--------------------------|
> | **A — Stand up this repo** | Run the service as-is and add the bug icon to *this* repo's UI. Start here to try it. |
> | **B — Integrate into an existing app** | Deploy this service alongside your own app and wire the bug icon into your existing frontend/backend. |
> | **C — Build it from scratch into your codebase** | Re-implement the service natively inside your existing stack (your backend, your DB, your conventions) using this repo as the reference spec. |
>
> B and C carry the hard-won gotchas (screenshot column must be unbounded, CORS private-network, no `data:` URIs in issue bodies, browser-reachable API URL) so your LLM doesn't rediscover them.

### Prompt A — stand up this repo and add the icon to its UI

````text
You are setting up the "auto-ticket-service" in this repository. It is a web
service that raises a GitHub issue when a user reports a bug from any UI.

Do the following, in order:

1. Read README.md, docs/INTEGRATION.md, and docs/API.md in this repo to learn the
   HTTP contract (POST /tickets, GET /tickets, GET /tickets/new, GET /health).

2. Start the stack locally in mock mode (no credentials needed):
     cp .env.example .env
     docker compose up --build -d
   Then verify:
     - http://localhost:8000/health  returns {"status":"ok","mode":"mock",...}
     - http://localhost:8000/docs    shows the Swagger UI
     - http://localhost:8501         shows the demo UI with a red 🐞 button (bottom-right)
   Raise a test ticket by clicking the 🐞 button, and confirm it appears under the
   "Issues feed" tab.

3. To make it open REAL GitHub issues, edit .env:
     MOCK_GITHUB=false
     GITHUB_TOKEN=<a PAT with "Issues: read & write" on the target repo>
     GITHUB_REPO=<owner/name>
   then `docker compose up -d --build api`. Confirm /health shows "mode":"github".

4. Integrate the bug icon into THIS project's UI:
   - Identify the frontend framework in use (look for package.json / *.swift /
     templates) and tell me what it is before writing code.
   - Add a floating bug button following the pattern in docs/INTEGRATION.md for that
     framework. On click it collects {title, body, category, source, reporter,
     optional screenshot} and POSTs to the auto-ticket service's /tickets endpoint.
   - Point it at the service via an API_URL env var; do not hardcode the host.

5. Show me a diff of everything you changed and the exact commands to run it. Do not
   commit or push anything unless I explicitly ask.

Constraints: keep the service itself unmodified unless I ask for a feature change.
Treat GITHUB_TOKEN as a secret — never print it or write it into committed files.
````

### Prompt B — integrate this service into an existing app

> Run this from **your existing project's** repo root. It has `auto-ticket-service`
> available as a sibling folder, a git submodule, or a cloned path — tell the LLM where.

````text
You are integrating the "auto-ticket-service" (a web service that raises a GitHub
issue from any UI) into THIS existing application. The service's source is available
at: <PATH-OR-URL to auto-ticket-service — e.g. ../auto-ticket-service>.

Do the following, in order. Ask me before any step you're unsure about; do not commit
or push unless I say so.

1. Read, in the auto-ticket-service repo: README.md, docs/API.md, docs/INTEGRATION.md,
   docs/ARCHITECTURE.md. The HTTP contract you'll use: POST /tickets (+ /tickets/multipart
   for a screenshot), GET /tickets, GET /tickets/new, GET /health.

2. Inspect THIS project first and report back before writing code:
   - the frontend framework(s) (package.json, *.swift, templates) and where a global
     overlay/component can live so a bug icon shows on every screen;
   - how this project runs locally (docker-compose? a dev server?) and how it manages
     secrets and env vars;
   - the origin(s) the UI is served from (for CORS).

3. Deploy the service next to this app:
   - If this project uses docker-compose, add the service's `db` + `api` services to it
     (copy from auto-ticket-service/docker-compose.yml). Reuse this project's Postgres if
     it has one (point DATABASE_URL at a separate database/schema), else add the provided db.
   - Configure it: MOCK_GITHUB=false, GITHUB_TOKEN (a PAT with Issues: read & write, from
     this project's secret store — never hardcoded), GITHUB_REPO=<owner/name>.
   - Set the API's CORS_ORIGINS to this UI's exact origin(s), not "*".
   - Verify GET /health shows {"mode":"github", "repo": ...}.

4. Add the bug reporter to THIS app's UI:
   - Add a floating bug icon on every screen, following docs/INTEGRATION.md for the
     framework you found. Prefer the screenshot+annotate flow (html2canvas capture → draw
     with a marker → send) from ui/bug_widget.py; fall back to a simple form where that
     doesn't fit.
   - On send, POST to the service with {title, body, category, source:"<this-app>",
     reporter, meta:{route, app_version, ...}} and, if a screenshot, the /tickets/multipart
     endpoint.
   - Point the client at the service via a BROWSER-REACHABLE URL from config/env (e.g.
     TICKET_API), never an internal Docker hostname and never hardcoded.

5. (Optional) If this app has an admin/dashboard, add a "new issues" feed by polling
   GET /tickets/new?since=<last-check>.

6. Smoke-test end to end: raise a ticket from the UI, confirm a real GitHub issue opens
   and the returned link works. Then show me a diff of everything you changed and the
   commands to run it.

Watch out for (these are real, already-solved issues in the service — keep them working):
   - Post from the browser to a browser-reachable API URL; internal hostnames won't resolve
     in the user's browser.
   - If the icon renders inside a sandboxed iframe (e.g. a Streamlit/embedded component),
     the API needs CORS allow_private_network=True or Chrome blocks localhost with
     "TypeError: Failed to fetch".
   - Treat GITHUB_TOKEN as a secret; keep it server-side only.
````

### Prompt C — build the service from scratch inside your existing solution

> Use this when you don't want a separate service — you want the same capability
> implemented natively in your existing backend, DB, and conventions, with this repo
> as the reference spec.

````text
You are ADDING an "auto-ticket" capability to THIS existing solution: report a bug from
any UI and it opens a GitHub issue, plus auto-discover issues opened on GitHub. Do NOT
run the reference repo as a separate service — re-implement it natively in this codebase,
matching our language, framework, DB, and conventions. Use the reference implementation at
<PATH-OR-URL to auto-ticket-service> as the spec to port from.

Do the following, in order. Report findings before writing code; don't commit/push unless
I say so.

1. Study the reference so you can port it faithfully:
   - docs/API.md and docs/ARCHITECTURE.md (the contract + design),
   - service/app/github.py     (GitHub REST client + a MOCK mode — port both),
   - service/app/tickets.py     (create-ticket + sync-from-GitHub logic),
   - service/app/models.py, schemas.py, routes.py, poller.py,
   - ui/bug_widget.py           (the screenshot+annotate bug widget).

2. Study THIS solution and propose a plan before coding:
   - the backend framework and where HTTP routes live;
   - the database and migration tool (so tickets get a proper migration, not create_all);
   - the frontend framework and where a global bug icon can mount;
   - config/secret handling and how background tasks run here (native scheduler vs. an
     asyncio loop).

3. Implement, natively in this codebase:
   - A `tickets` table/model. IMPORTANT: the screenshot column must be an UNBOUNDED text
     type — a captured screenshot is a base64 data: URI of tens of thousands of chars; a
     varchar(N) will overflow (this bit the reference implementation). Add it via this
     project's migration system.
   - A GitHub issues client with: idempotent label-ensure, best-effort discipline (NEVER
     let issue creation raise into the request — store the ticket regardless), and a MOCK
     mode gated on a config flag / missing token so the whole thing runs with no credentials.
   - Endpoints mirroring the contract: POST /tickets (+ multipart for a screenshot),
     GET /tickets, GET /tickets/{id}, GET /tickets/new, GET /health. Register static routes
     before parameterized ones.
   - When building the GitHub issue body, do NOT embed a data: URI screenshot (GitHub can't
     render it and it can exceed the ~65 KB body limit) — note the attachment and embed only
     real http(s) image URLs.
   - A background poller that syncs open GitHub issues into the table, de-duped by issue
     number, exposed via GET /tickets/new.
   - CORS for the UI origin. If the icon can render in a sandboxed iframe, enable
     private-network access on preflight (the "TypeError: Failed to fetch" gotcha).

4. Add the bug icon to this app's UI (screenshot capture → draw → send), pointed at the new
   endpoints via a browser-reachable, env-configured URL.

5. Add tests matching ours (credential-free: mock GitHub client + issue-body builder), and
   smoke-test end to end against a real repo (MOCK off) — confirm an issue opens and its link
   works. Show me the plan first, then the diff.

Config: MOCK flag, GITHUB_TOKEN (secret, server-side only), GITHUB_REPO, poll interval,
CORS origins — all from this project's config system, nothing hardcoded.
````

---

## Quickstart (without Claude Code)

```bash
cp .env.example .env          # defaults to MOCK_GITHUB=true — no credentials needed
docker compose up --build     # builds service + UI, starts Postgres
```

| What | URL |
|------|-----|
| Demo UI (mock host app + 🐞 icon) | http://localhost:8501 |
| API — Swagger docs | http://localhost:8000/docs |
| API — health/mode | http://localhost:8000/health |

Tap the red **🐞** button at the bottom-right (exactly like the iOS ladybug flow):
it **screenshots the current screen**, lets you **draw on it with a red marker** to
circle the problem, then add a title/description and **Send** — no file upload. In
mock mode a fake issue (`#1001`, …) is created with your annotated screenshot
attached; open the **Issues feed** tab to see it.

### Point it at a real GitHub repo

Edit `.env`:

```env
MOCK_GITHUB=false
GITHUB_TOKEN=github_pat_xxxx…      # Issues: read & write on the repo
GITHUB_REPO=your-org/your-repo
```

```bash
docker compose up -d --build api
curl -s localhost:8000/health | jq   # "mode" should now be "github"
```

Every ticket now opens a real issue in `your-org/your-repo`, and the poller imports
issues opened directly on GitHub into the feed.

---

## What you get

```
┌────────────┐   POST /tickets    ┌──────────────────┐   REST    ┌──────────┐
│  Any UI    │ ─────────────────▶ │  auto-ticket-svc │ ────────▶ │  GitHub  │
│ (🐞 icon)  │                    │   (FastAPI)      │  issues   │  Issues  │
└────────────┘ ◀───────────────── └──────────────────┘ ◀──────── └──────────┘
      ▲          GET /tickets            │    ▲          poll (auto-check)
      │                                  ▼    │
      │                            ┌──────────────┐
      └────────────────────────────│  Postgres    │  (source of truth for the UI)
             GET /tickets/new      └──────────────┘
```

- **Any UI** (web, mobile, another Streamlit/React app) shows a bug icon and calls `POST /tickets`.
- The **service** opens a GitHub issue and records the ticket in Postgres.
- The **poller** periodically syncs open issues from GitHub back into Postgres, so a UI can show *newly filed* issues via `GET /tickets/new` — the **auto-check for new issues** feature.

---

## Repository layout

```
auto-ticket-service/
├── docker-compose.yml       # db + api + ui, one command
├── .env.example             # copy to .env
├── README.md                # you are here
├── CLAUDE.md                # repo guide for LLM coding agents
├── service/                 # the FastAPI web service
│   ├── app/
│   │   ├── main.py          # FastAPI app + lifespan (starts poller)
│   │   ├── config.py        # env-driven settings, mock-mode logic
│   │   ├── routes.py        # HTTP API (the public contract)
│   │   ├── schemas.py       # request/response models
│   │   ├── tickets.py       # create-ticket + sync-from-github logic
│   │   ├── github.py        # GitHub REST client (+ mock)
│   │   ├── poller.py        # background auto-check loop
│   │   ├── models.py        # Ticket table
│   │   └── database.py      # async engine/session
│   ├── tests/test_core.py   # credential-free unit tests
│   ├── Dockerfile
│   └── requirements.txt
├── ui/                      # Streamlit demo (mock host app + 🐞 FAB)
│   ├── app.py               # page chrome + issues feed
│   ├── bug_widget.py        # self-contained screenshot+draw+send widget (html2canvas)
│   ├── Dockerfile
│   └── requirements.txt
└── docs/
    ├── API.md               # endpoint reference
    ├── INTEGRATION.md       # add the bug icon to your own UI/backend
    └── ARCHITECTURE.md      # how it works + design decisions
```

---

## Documentation

- **[docs/API.md](docs/API.md)** — every endpoint, with request/response examples.
- **[docs/INTEGRATION.md](docs/INTEGRATION.md)** — drop the 🐞 bug icon into React, plain JS, Swift/iOS, or call the service from a backend; includes the "auto-check for new issues" polling pattern.
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — design decisions, mock mode, the poller, and how to harden for production.

## Local development (without Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r service/requirements.txt
# needs a Postgres; or run just the db from compose:  docker compose up -d db
export DATABASE_URL=postgresql+asyncpg://tickets:tickets@localhost:5432/tickets
export MOCK_GITHUB=true
cd service && uvicorn app.main:app --reload
```

Run the tests (no DB, no network needed):

```bash
cd service && MOCK_GITHUB=true python -m pytest -q
```

## Security notes

- `GITHUB_TOKEN` is a secret: it lives only in `.env` (git-ignored) / your orchestrator's secret store — never in code or images.
- The create endpoint is unauthenticated by default (fine behind your own gateway / for internal tools). For public exposure, put it behind auth and restrict `CORS_ORIGINS` to your UI's origin. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#hardening-for-production).
