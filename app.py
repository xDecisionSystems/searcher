import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query

APP_USER_AGENT = os.getenv(
    "MCP_USER_AGENT",
    "searcher-mcp/1.0 (+https://localhost)",
)
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
PDF_MAX_MB = int(os.getenv("PDF_MAX_MB", "50"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", tempfile.gettempdir()))
VERSION_FILE = Path(__file__).with_name("VERSION.md")

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY")
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")


def _load_version_name() -> str:
    default_version_name = os.getenv("VERSION_NAME", "searcher-mcp-dev")
    try:
        content = VERSION_FILE.read_text(encoding="utf-8")
    except OSError:
        return default_version_name

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("VERSION_NAME="):
            value = line.split("=", 1)[1].strip()
            return value.strip("'\"") or default_version_name
    return default_version_name


VERSION_NAME = _load_version_name()

session = requests.Session()
session.headers.update({"User-Agent": APP_USER_AGENT})

app = FastAPI(title="Searcher MCP API", version=VERSION_NAME)


def _validate_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL. Use http(s) URL.")


def _request_json(url: str, **kwargs: Any) -> dict[str, Any]:
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Upstream did not return valid JSON.") from exc


def _search_web_serpapi(query: str, limit: int) -> list[dict[str, str]]:
    if not SERPAPI_API_KEY:
        raise HTTPException(status_code=400, detail="SERPAPI_API_KEY is not configured.")
    payload = _request_json(
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": query, "num": limit, "api_key": SERPAPI_API_KEY},
    )
    results: list[dict[str, str]] = []
    for item in payload.get("organic_results", [])[:limit]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
        )
    return results


def _search_web_brave(query: str, limit: int) -> list[dict[str, str]]:
    if not BRAVE_SEARCH_API_KEY:
        raise HTTPException(status_code=400, detail="BRAVE_SEARCH_API_KEY is not configured.")
    payload = _request_json(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": limit},
        headers={"X-Subscription-Token": BRAVE_SEARCH_API_KEY},
    )
    results: list[dict[str, str]] = []
    for item in payload.get("web", {}).get("results", [])[:limit]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            }
        )
    return results


def _search_web_bing(query: str, limit: int) -> list[dict[str, str]]:
    if not BING_SEARCH_API_KEY:
        raise HTTPException(status_code=400, detail="BING_SEARCH_API_KEY is not configured.")
    payload = _request_json(
        "https://api.bing.microsoft.com/v7.0/search",
        params={"q": query, "count": limit},
        headers={"Ocp-Apim-Subscription-Key": BING_SEARCH_API_KEY},
    )
    results: list[dict[str, str]] = []
    for item in payload.get("webPages", {}).get("value", [])[:limit]:
        results.append(
            {
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
            }
        )
    return results


def _search_web_duckduckgo(query: str, limit: int) -> list[dict[str, str]]:
    # No API key fallback when paid providers are not configured.
    try:
        resp = session.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"DuckDuckGo request failed: {exc}") from exc

    soup = BeautifulSoup(resp.text, "html.parser")
    results: list[dict[str, str]] = []
    for node in soup.select("div.result")[:limit]:
        anchor = node.select_one("a.result__a")
        snippet = node.select_one(".result__snippet")
        if not anchor:
            continue
        href = anchor.get("href", "")
        results.append(
            {
                "title": anchor.get_text(strip=True),
                "url": href,
                "snippet": snippet.get_text(" ", strip=True) if snippet else "",
            }
        )
    return results


def _search_scholar_semantic(query: str, limit: int) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    return _request_json(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={
            "query": query,
            "limit": limit,
            "fields": "title,year,authors,url,abstract,openAccessPdf,citationCount",
        },
        headers=headers or None,
    )


def _search_scholar_serpapi(query: str, limit: int) -> dict[str, Any]:
    if not SERPAPI_API_KEY:
        raise HTTPException(status_code=400, detail="SERPAPI_API_KEY is not configured.")
    payload = _request_json(
        "https://serpapi.com/search.json",
        params={
            "engine": "google_scholar",
            "q": query,
            "num": limit,
            "api_key": SERPAPI_API_KEY,
        },
    )
    results: list[dict[str, Any]] = []
    for item in payload.get("organic_results", [])[:limit]:
        resources = item.get("resources", [])
        pdf_link = ""
        for resource in resources:
            if "pdf" in resource.get("file_format", "").lower():
                pdf_link = resource.get("link", "")
                break
        results.append(
            {
                "title": item.get("title"),
                "publication_info": item.get("publication_info"),
                "snippet": item.get("snippet"),
                "result_id": item.get("result_id"),
                "link": item.get("link"),
                "pdf_link": pdf_link,
            }
        )
    return {"data": results}


def _extract_page_content(html: str, max_chars: int) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements for cleaner text extraction.
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else ""
    meta_description = ""
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta and meta.get("content"):
        meta_description = str(meta.get("content")).strip()

    body_text = soup.get_text(separator=" ", strip=True)
    if len(body_text) > max_chars:
        body_text = body_text[:max_chars]

    links: list[str] = []
    for anchor in soup.select("a[href]")[:25]:
        href = str(anchor.get("href", "")).strip()
        if href:
            links.append(href)

    return {
        "title": title,
        "meta_description": meta_description,
        "text": body_text,
        "links": links,
    }


def _review_page_content(html: str, max_chars: int) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    extracted = _extract_page_content(html=html, max_chars=max_chars)
    headings = [h.get_text(" ", strip=True) for h in soup.select("h1, h2, h3")[:15]]
    text = extracted["text"]
    words = text.split()
    return {
        **extracted,
        "word_count": len(words),
        "estimated_read_time_minutes": max(1, round(len(words) / 220)),
        "headings": headings,
    }


def _build_pdf_filename(url: str) -> str:
    parsed = urlparse(url)
    raw_name = Path(parsed.path).name or "downloaded_paper.pdf"
    if not raw_name.lower().endswith(".pdf"):
        raw_name = f"{raw_name}.pdf"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name)
    return safe_name[:200]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version_name": VERSION_NAME}


@app.get("/search_web")
def search_web(
    query: str,
    limit: int = Query(default=5, ge=1, le=20),
    provider: str = Query(default="auto"),
) -> dict[str, Any]:
    provider = provider.lower()
    if provider == "auto":
        if SERPAPI_API_KEY:
            provider = "serpapi_google"
        elif BRAVE_SEARCH_API_KEY:
            provider = "brave"
        elif BING_SEARCH_API_KEY:
            provider = "bing"
        else:
            provider = "duckduckgo"

    if provider == "serpapi_google":
        results = _search_web_serpapi(query, limit)
    elif provider == "brave":
        results = _search_web_brave(query, limit)
    elif provider == "bing":
        results = _search_web_bing(query, limit)
    elif provider == "duckduckgo":
        results = _search_web_duckduckgo(query, limit)
    else:
        raise HTTPException(status_code=400, detail="Invalid provider.")

    return {"provider": provider, "query": query, "results": results}


@app.get("/search_google")
def search_google(
    query: str,
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    results = _search_web_serpapi(query=query, limit=limit)
    return {"provider": "serpapi_google", "query": query, "results": results}


@app.get("/fetch_page")
def fetch_page(
    url: str,
    include_html: bool = Query(default=False),
    max_chars: int = Query(default=12000, ge=500, le=100000),
) -> dict[str, Any]:
    _validate_http_url(url)
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch page: {exc}") from exc

    html = resp.text
    extracted = _extract_page_content(html, max_chars=max_chars)
    payload: dict[str, Any] = {"url": url, **extracted}
    if include_html:
        payload["html"] = html
    return payload


@app.get("/review_page")
def review_page(
    url: str,
    include_html: bool = Query(default=False),
    max_chars: int = Query(default=12000, ge=500, le=100000),
) -> dict[str, Any]:
    _validate_http_url(url)
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch page: {exc}") from exc

    html = resp.text
    review = _review_page_content(html=html, max_chars=max_chars)
    payload: dict[str, Any] = {"url": url, **review}
    if include_html:
        payload["html"] = html
    return payload


@app.get("/search_scholar")
def search_scholar(
    query: str,
    limit: int = Query(default=5, ge=1, le=20),
    provider: str = Query(default="auto"),
) -> dict[str, Any]:
    provider = provider.lower()
    if provider == "auto":
        provider = "semantic_scholar"

    if provider == "semantic_scholar":
        data = _search_scholar_semantic(query, limit)
    elif provider == "google_scholar_serpapi":
        data = _search_scholar_serpapi(query, limit)
    else:
        raise HTTPException(status_code=400, detail="Invalid provider.")
    return {"provider": provider, "query": query, **data}


@app.get("/search_google_scholar")
def search_google_scholar(
    query: str,
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    data = _search_scholar_serpapi(query=query, limit=limit)
    return {"provider": "google_scholar_serpapi", "query": query, **data}


@app.get("/download_pdf")
def download_pdf(url: str) -> dict[str, Any]:
    _validate_http_url(url)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = _build_pdf_filename(url)
    out_path = DOWNLOAD_DIR / filename
    max_bytes = PDF_MAX_MB * 1024 * 1024
    size = 0

    try:
        with session.get(url, stream=True, timeout=REQUEST_TIMEOUT) as resp:
            resp.raise_for_status()
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail=f"URL does not appear to be a PDF (Content-Type: {content_type}).",
                )

            with open(out_path, "wb") as file_handle:
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"PDF exceeded configured max size ({PDF_MAX_MB} MB).",
                        )
                    file_handle.write(chunk)
    except HTTPException:
        if out_path.exists():
            out_path.unlink()
        raise
    except requests.RequestException as exc:
        if out_path.exists():
            out_path.unlink()
        raise HTTPException(status_code=502, detail=f"Failed to download PDF: {exc}") from exc

    return {"path": str(out_path), "size_bytes": size, "filename": filename}
