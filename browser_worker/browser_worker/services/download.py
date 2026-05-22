import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from ..config import APP_USER_AGENT, DOWNLOAD_DIR, HEADLESS, MAX_DOWNLOAD_MB, REQUEST_TIMEOUT


def _validate_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL. Use http(s) URL.")


def _safe_filename(url: str, fallback_prefix: str = "paper") -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name.strip() or f"{fallback_prefix}-{uuid.uuid4().hex}.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:220]


def _unique_output_path(directory: Path, filename: str) -> Path:
    """Return a path that does not exist by appending a short UUID when needed."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = filename[:-4] if filename.lower().endswith(".pdf") else filename
    return directory / f"{stem}-{uuid.uuid4().hex[:8]}.pdf"


def _stream_to_disk(url: str, out_path: Path) -> int:
    """Download url via requests streaming, enforce MAX_DOWNLOAD_MB, write to out_path."""
    max_bytes = MAX_DOWNLOAD_MB * 1024 * 1024
    size = 0
    try:
        with requests.get(
            url,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": APP_USER_AGENT},
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            with open(out_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Download exceeded configured max size ({MAX_DOWNLOAD_MB} MB).",
                        )
                    fh.write(chunk)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Download request failed: {exc}") from exc
    return size


def _extract_pdf_link(base_url: str, html: str) -> str | None:
    """Return the best PDF link found on the page, or None.

    Priority order:
    1. <a> whose href ends with .pdf (explicit extension)
    2. <a> whose link text contains "pdf" (case-insensitive)
    3. <a> whose href contains "pdf" (fallback)

    Only http/https absolute or root-relative hrefs are considered.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[int, str]] = []

    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue

        lower_href = href.lower()
        link_text = anchor.get_text(" ", strip=True).lower()

        if lower_href.endswith(".pdf"):
            candidates.append((0, absolute))
        elif "pdf" in link_text:
            candidates.append((1, absolute))
        elif "pdf" in lower_href:
            candidates.append((2, absolute))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _get_browser_context(playwright: Any) -> Any:
    """Return a browser context.

    Priority:
    1. CDP_URL set — connect to a remote Chromium instance (session lives there).
    2. SESSION_DIR set — launch a persistent local context (cookies saved to disk).
    3. Neither — launch a fresh ephemeral context per request.
    """
    from ..config import CDP_URL, HEADLESS, SESSION_DIR

    if CDP_URL:
        browser = playwright.chromium.connect_over_cdp(CDP_URL)
        # Reuse the default context that Chromium was started with so the
        # persistent session (cookies, storage) is available.
        contexts = browser.contexts
        if contexts:
            return contexts[0]
        return browser.new_context(user_agent=APP_USER_AGENT)

    if SESSION_DIR is not None:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        return playwright.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=HEADLESS,
            user_agent=APP_USER_AGENT,
        )

    browser = playwright.chromium.launch(headless=HEADLESS)
    return browser.new_context(user_agent=APP_USER_AGENT)


def _close_context_if_needed(ctx: Any) -> None:
    """Close context only for local launches; keep shared CDP context alive."""
    from ..config import CDP_URL

    if CDP_URL:
        return
    ctx.close()


def _navigate_for_analysis(page: Any, url: str) -> tuple[Any | None, str, str]:
    """Navigate to URL and return response, final URL, and HTML snapshot.

    Some auth handoff flows (for example EZproxy) can raise ERR_ABORTED while
    still landing the browser on a useful login URL. Treat that case as
    recoverable so callers can decide whether to prompt for login.
    """
    aborted = False
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=int(REQUEST_TIMEOUT * 1000))
    except PlaywrightError as exc:
        if "ERR_ABORTED" not in str(exc):
            raise
        response = None
        aborted = True

    try:
        current_url = page.url
    except PlaywrightError:
        current_url = url
    try:
        html = page.content()
    except PlaywrightError:
        html = ""

    # ERR_ABORTED on EZproxy/auth redirects: the page is in a broken state.
    # Signal login_required via synthetic HTML so callers detect it correctly.
    if aborted and not html:
        html = "<html><body><p>login</p><p>sign in</p></body></html>"

    return response, current_url, html


def _open_url_in_novnc(ctx: Any, url: str) -> Any:
    """Open url in a new tab and bring it to the front in noVNC. Returns the page."""
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
    except PlaywrightError:
        pass
    try:
        page.bring_to_front()
    except PlaywrightError:
        pass
    return page


def _is_login_page(html: str, url: str) -> bool:
    """Heuristic: returns True if the page looks like a login wall."""
    lower = html.lower()
    login_signals = [
        "sign in", "log in", "login", "please sign", "access denied",
        "institutional access", "subscribe", "purchase access",
        "you need to", "register to", "create account",
    ]
    # Also check if we've been redirected to an auth domain
    auth_domains = ["login.", "accounts.", "auth.", "shibboleth.", "idp."]
    from urllib.parse import urlparse as _up
    domain = _up(url).netloc.lower()
    if any(d in domain for d in auth_domains):
        return True
    matched = sum(1 for s in login_signals if s in lower)
    return matched >= 2


def _login_required_response(requested_url: str, current_url: str) -> dict[str, Any]:
    from ..config import NOVNC_URL

    return {
        "status": "login_required",
        "requires_login": True,
        "message": (
            "Login is required to download this paper. "
            "The login page has been opened in the remote browser."
        ),
        "requested_url": requested_url,
        "current_url": current_url,
        "novnc_url": NOVNC_URL,
        "user_prompt": (
            f"A login page has been opened in the browser at {NOVNC_URL} — "
            "please log in there, then press **OK** to retry the download, "
            "or press **Stop** to cancel."
        ),
        "retry_recommended": True,
        "method": "interactive_login_required",
    }



def download_paper_via_browser(url: str, filename: str | None = None) -> dict[str, Any]:
    _validate_http_url(url)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    base_name = filename.strip() if filename else _safe_filename(url)
    if not base_name.lower().endswith(".pdf"):
        base_name = f"{base_name}.pdf"
    base_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)[:220]
    output_path = _unique_output_path(DOWNLOAD_DIR, base_name)

    try:
        with sync_playwright() as playwright:
            ctx = _get_browser_context(playwright)

            page = ctx.new_page()

            response, current_url, html = _navigate_for_analysis(page, url)
            content_type = ""
            if response is not None:
                content_type = (response.header_value("content-type") or "").lower()

            if "pdf" in content_type:
                # Page response is directly a PDF — get the final URL and stream it
                final_url = page.url
                page.close()
                _close_context_if_needed(ctx)
                size = _stream_to_disk(final_url, output_path)
                return {
                    "path": str(output_path),
                    "filename": output_path.name,
                    "size_bytes": size,
                    "source_url": final_url,
                    "method": "browser_direct_stream",
                }

            if _is_login_page(html, current_url):
                # If the page state is broken (ERR_ABORTED), open a fresh tab so
                # the user actually sees something in noVNC. The tab must stay open
                # after this function returns, so we do NOT close the context here.
                # With CDP the context is the shared remote browser — exiting the
                # sync_playwright() block disconnects our client but leaves the
                # remote tab open.
                if not html or html.strip() == "<html><body><p>login</p><p>sign in</p></body></html>":
                    try:
                        page.close()
                    except PlaywrightError:
                        pass
                    _open_url_in_novnc(ctx, url)
                else:
                    try:
                        page.bring_to_front()
                    except PlaywrightError:
                        pass
                # Return inside the with-block so the playwright client is still
                # connected when bring_to_front / goto complete, then disconnect.
                login_response = _login_required_response(url, current_url)
                # Don't close the context — the tab must remain open for the user.
                return login_response

            page.close()
            _close_context_if_needed(ctx)

        pdf_link = _extract_pdf_link(current_url, html)
        if not pdf_link:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No PDF link found on page using browser automation. "
                    "The page may require interactive login/navigation."
                ),
            )

        size = _stream_to_disk(pdf_link, output_path)
        return {
            "path": str(output_path),
            "filename": output_path.name,
            "size_bytes": size,
            "source_url": pdf_link,
            "method": "browser_page_pdf_link",
        }

    except HTTPException:
        if output_path.exists():
            output_path.unlink()
        raise
    except PlaywrightError as exc:
        if output_path.exists():
            output_path.unlink()
        raise HTTPException(status_code=502, detail=f"Browser automation failed: {exc}") from exc
