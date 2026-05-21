from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import VERSION_NAME
from .services.download import download_paper_authenticated, download_paper_via_browser

app = FastAPI(title="Searcher Browser Worker", version=VERSION_NAME)


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
