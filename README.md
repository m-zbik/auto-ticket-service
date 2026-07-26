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

> **New developer? Paste the block below into [Claude Code](https://claude.com/claude-code) from the repo root.** It gives the LLM everything it needs to stand the service up and integrate the bug icon into *your* app.

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
