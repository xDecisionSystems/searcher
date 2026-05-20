from typing import Any

import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException

from ..config import (
    BING_SEARCH_API_KEY,
    BRAVE_SEARCH_API_KEY,
    REQUEST_TIMEOUT,
    SEMANTIC_SCHOLAR_API_KEY,
    SERPAPI_API_KEY,
    SERPER_API_KEY,
)
from ..http_client import request_json, session


def _search_web_serpapi(query: str, limit: int) -> list[dict[str, str]]:
    if not SERPAPI_API_KEY:
        raise HTTPException(status_code=400, detail="SERPAPI_API_KEY is not configured.")
    payload = request_json(
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


def _search_web_serper(query: str, limit: int) -> list[dict[str, str]]:
    if not SERPER_API_KEY:
        raise HTTPException(status_code=400, detail="SERPER_API_KEY is not configured.")
    payload = request_json(
        "https://google.serper.dev/search",
        method="POST",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": limit},
    )
    results: list[dict[str, str]] = []
    for item in payload.get("organic", [])[:limit]:
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
    payload = request_json(
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
    payload = request_json(
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
    return request_json(
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
    payload = request_json(
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


def search_web(query: str, limit: int, provider: str) -> dict[str, Any]:
    provider = provider.lower()
    if provider == "auto":
        if SERPAPI_API_KEY:
            provider = "serpapi_google"
        elif SERPER_API_KEY:
            provider = "serper_google"
        elif BRAVE_SEARCH_API_KEY:
            provider = "brave"
        elif BING_SEARCH_API_KEY:
            provider = "bing"
        else:
            provider = "duckduckgo"

    if provider == "serpapi_google":
        results = _search_web_serpapi(query, limit)
    elif provider == "serper_google":
        results = _search_web_serper(query, limit)
    elif provider == "brave":
        results = _search_web_brave(query, limit)
    elif provider == "bing":
        results = _search_web_bing(query, limit)
    elif provider == "duckduckgo":
        results = _search_web_duckduckgo(query, limit)
    else:
        raise HTTPException(status_code=400, detail="Invalid provider.")

    return {"provider": provider, "query": query, "results": results}


def search_google(query: str, limit: int) -> dict[str, Any]:
    if SERPAPI_API_KEY:
        provider = "serpapi_google"
        results = _search_web_serpapi(query=query, limit=limit)
    elif SERPER_API_KEY:
        provider = "serper_google"
        results = _search_web_serper(query=query, limit=limit)
    else:
        raise HTTPException(
            status_code=400,
            detail="Set SERPAPI_API_KEY or SERPER_API_KEY to use /search_google.",
        )
    return {"provider": provider, "query": query, "results": results}


def search_scholar(query: str, limit: int, provider: str) -> dict[str, Any]:
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


def search_google_scholar(query: str, limit: int) -> dict[str, Any]:
    data = _search_scholar_serpapi(query=query, limit=limit)
    return {"provider": "google_scholar_serpapi", "query": query, **data}
