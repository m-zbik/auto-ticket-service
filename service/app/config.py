"""Runtime configuration for the auto-ticket service.

Every setting is environment-driven so the same image runs unchanged in local
Docker, CI, and production. Copy `.env.example` to `.env` and fill in the two
things that matter for real use: GITHUB_TOKEN and GITHUB_REPO.

Set MOCK_GITHUB=true (the default in docker-compose) to run the whole stack with
NO GitHub credentials — issues are simulated and stored in Postgres so you can
demo the UI end-to-end offline.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- GitHub ---
    github_token: str = ""                       # repo/issues write scope; unset ⇒ implies mock
    github_repo: str = "owner/repo"              # "owner/name" the issues land in
    mock_github: bool = False                    # simulate GitHub instead of calling it

    # --- Storage ---
    database_url: str = (
        "postgresql+asyncpg://tickets:tickets@db:5432/tickets"
    )

    # --- Poller (auto-check for new issues) ---
    poll_enabled: bool = True
    poll_interval_seconds: int = 60              # how often to sync issues from GitHub

    # --- Service ---
    service_name: str = "auto-ticket-service"
    cors_origins: str = "*"                      # comma-separated; "*" allows any UI

    @property
    def use_mock(self) -> bool:
        """Mock when explicitly asked, or whenever no token is available."""
        return self.mock_github or not self.github_token

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
