from typing import Any

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, Field

from .config import VERSION_NAME
from .services.download import download_paper_authenticated, download_paper_via_browser

app = FastAPI(
    title="Searcher Browser Worker",
    description=(
        "Browser-automation service for downloading academic papers from authenticated "
        "publisher portals. Opens pages in a real Chromium browser and can prompt "
        "interactive login through noVNC when needed."
    ),
    version=VERSION_NAME,
)


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Target page URL that should eventually lead to a PDF.")
    filename: str | None = Field(default=None, description="Optional output filename.")


class AuthenticatedDownloadRequest(BaseModel):
    url: str = Field(..., description="Target page URL (may require login).")
    filename: str | None = Field(default=None, description="Optional output filename.")
    poll_interval: int = Field(default=30, ge=5, le=300, description="Seconds between retries when login is required.")
    max_wait_minutes: int = Field(default=10, ge=1, le=60, description="Maximum minutes to wait for login.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "browser_worker", "version_name": VERSION_NAME}


@app.post("/download_paper")
def download_paper(request: DownloadRequest) -> dict[str, Any]:
    """Attempt download immediately.

    When a login wall is detected, returns a structured login_required response
    so MCP agents can prompt the user to log in via noVNC and retry after
    confirmation.
    """
    return download_paper_via_browser(url=request.url, filename=request.filename)


@app.post("/download_paper_authenticated")
def download_paper_auth(request: AuthenticatedDownloadRequest) -> dict[str, Any]:
    """Download a paper that may require institutional login.

    Opens the URL in the noVNC Chromium browser. If a login wall is detected,
    leaves the page open for the user to log in via noVNC, then retries every
    poll_interval seconds until the paper is accessible or max_wait_minutes is reached.
    """
    return download_paper_authenticated(
        url=request.url,
        filename=request.filename,
        poll_interval=request.poll_interval,
        max_wait_minutes=request.max_wait_minutes,
    )


# ─── MCP server ───────────────────────────────────────────────────────────────
mcp = FastApiMCP(
    app,
    name="Browser Worker MCP",
    description=(
        "Download academic papers from publisher portals using a real Chromium browser. "
        "download_paper attempts immediate download; if login is required, it returns "
        "login_required instructions so the agent can ask the user to log in via noVNC "
        "and retry after the user confirms Yes."
    ),
    exclude_operations=["health"],
)
mcp.mount()
