from typing import Any

from fastapi import FastAPI, Query

from .config import VERSION_NAME
from .services.page import fetch_page as fetch_page_service
from .services.page import review_page as review_page_service
from .services.pdf import download_pdf as download_pdf_service
from .services.search import (
    search_google as search_google_service,
    search_google_scholar as search_google_scholar_service,
    search_scholar as search_scholar_service,
    search_web as search_web_service,
)

app = FastAPI(title="Searcher MCP API", version=VERSION_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version_name": VERSION_NAME}


@app.get("/search_web")
def search_web(
    query: str,
    limit: int = Query(default=5, ge=1, le=20),
    provider: str = Query(default="auto"),
) -> dict[str, Any]:
    return search_web_service(query=query, limit=limit, provider=provider)


@app.get("/search_google")
def search_google(
    query: str,
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    return search_google_service(query=query, limit=limit)


@app.get("/fetch_page")
def fetch_page(
    url: str,
    include_html: bool = Query(default=False),
    max_chars: int = Query(default=12000, ge=500, le=100000),
) -> dict[str, Any]:
    return fetch_page_service(url=url, include_html=include_html, max_chars=max_chars)


@app.get("/review_page")
def review_page(
    url: str,
    include_html: bool = Query(default=False),
    max_chars: int = Query(default=12000, ge=500, le=100000),
) -> dict[str, Any]:
    return review_page_service(url=url, include_html=include_html, max_chars=max_chars)


@app.get("/search_scholar")
def search_scholar(
    query: str,
    limit: int = Query(default=5, ge=1, le=20),
    provider: str = Query(default="auto"),
) -> dict[str, Any]:
    return search_scholar_service(query=query, limit=limit, provider=provider)


@app.get("/search_google_scholar")
def search_google_scholar(
    query: str,
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    return search_google_scholar_service(query=query, limit=limit)


@app.get("/download_pdf")
def download_pdf(url: str) -> dict[str, int | str]:
    return download_pdf_service(url=url)
