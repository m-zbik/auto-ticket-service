"""FastAPI entrypoint for the auto-ticket service.

Starts the DB, mounts the API, and launches the background poller. Interactive
docs at /docs (Swagger) and /redoc once running.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import poller
from app.config import get_settings
from app.database import init_db
from app.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    logger.info(
        "%s starting — mode=%s repo=%s",
        settings.service_name, "mock" if settings.use_mock else "github", settings.github_repo,
    )
    poller.start()
    yield
    await poller.stop()


settings = get_settings()
app = FastAPI(
    title="Auto-Ticket Service",
    description=(
        "Raise a GitHub issue from any UI or backend with one HTTP call, and "
        "auto-discover issues opened directly on GitHub. See /docs."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    # A UI widget in a sandboxed iframe (e.g. a Streamlit component) has an opaque
    # origin, which Chrome treats as a "public" address space. Its fetch to this
    # service on localhost is then a public→private request, which Chrome blocks
    # (surfacing as "TypeError: Failed to fetch") unless the preflight is answered
    # with `Access-Control-Allow-Private-Network: true`. This opts in.
    allow_private_network=True,
)

app.include_router(router)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"service": settings.service_name, "docs": "/docs", "health": "/health"}
