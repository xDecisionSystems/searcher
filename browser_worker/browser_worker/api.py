from typing import Any

from fastapi import FastAPI, Query
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, Field

from .config import VERSION_NAME
from .logger import tail_log
from .services.download import download_paper_via_browser

app = FastAPI(
    title="Searcher Browser Worker",
    description=(
        "Browser-automation service for downloading academic papers from authenticated "
        "publisher portals. Opens pages in a real Chromium browser and prompts "
        "interactive login through noVNC when needed."
    ),
    version=VERSION_NAME,
)


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Target page URL that should eventually lead to a PDF.")
    filename: str = Field(default="", description="Optional output filename. Leave empty to auto-generate.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "browser_worker", "version_name": VERSION_NAME}


@app.get("/logs")
def get_logs(
    n: int = Query(default=50, ge=1, le=500, description="Number of recent events to return."),
) -> dict[str, Any]:
    """Return the last n structured log events from the browser_worker event log.

    Use this to diagnose download failures: events include page navigation outcomes,
    HTTP status codes, which PDF selectors were tried, login detection signals,
    and final success/failure reasons.
    """
    events = tail_log(n)
    return {"count": len(events), "events": events}


@app.post("/download_paper")
def download_paper(request: DownloadRequest) -> dict[str, Any]:
    """Download a paper via browser automation.

    On success returns the saved file path and size.

    When a login wall is detected, returns status='login_required' and a
    user_prompt asking the user to log in via noVNC then press OK to retry
    or Stop to cancel. The agent must surface that prompt to the user and,
    if the user presses OK, call this endpoint again with the same URL.
    """
    return download_paper_via_browser(url=request.url, filename=request.filename or None)


# ─── MCP server ───────────────────────────────────────────────────────────────
mcp = FastApiMCP(
    app,
    name="Browser Worker MCP",
    description=(
        "Download academic papers from publisher portals using a real Chromium browser. "
        "Call download_paper with the paper URL. "
        "If the response has status='login_required', show the user_prompt to the user "
        "and wait for them to press OK (then retry the same call) or Stop (then abort). "
        "Do not retry automatically — always wait for explicit user confirmation. "
        "Call get_logs to inspect recent download events for self-diagnosis when a "
        "download fails or behaves unexpectedly."
    ),
    exclude_operations=["health"],
)
mcp.mount()
