# searcher

FastAPI service for scholarly search and web content retrieval. Part of the `searcher-stack` deployment.

## Endpoints

- `GET /health` — liveness check
- `GET /search_semantic_scholar` — Semantic Scholar (direct API)
- `GET /search_openalex` — OpenAlex (direct API, abstracts always included)
- `GET /search_ieeexplore` — IEEE Xplore (direct API)
- `GET /search_web_of_science` — Web of Science via Chromium browser
- `GET /search_scopus` — Elsevier Scopus (direct API)
- `GET /search_sciencedirect` — Elsevier ScienceDirect (direct API)
- `GET /search_ebsco` — EBSCO Research via Chromium browser
- `GET /search_google_scholar_browser` — Google Scholar via real Chromium browser (CAPTCHA-resistant)
- `GET /download_ebsco_paper` — download a single EBSCO paper by detail page URL
- `POST /download_ebsco_papers` — download multiple EBSCO papers sequentially
- `GET /fetch_page` — fetch and extract web page content
- `GET /review_page` — fetch page with headings, word count, read time
- `GET /download_pdf` — stream PDF to disk with size enforcement
- `GET /api-reference` — self-describing HTML API reference (for agents and humans)

## `search_google_scholar_browser` Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `query` | required | Search query string |
| `limit` | 200 | Number of results to return |
| `start_index` | 0 | Result offset for pagination |
| `year_low` | — | Earliest publication year (inclusive) |
| `year_high` | — | Latest publication year (inclusive) |
| `exclude_domains` | — | Domains to exclude (defaults to `researchgate.net`, `books.google.com`, `search.proquest.com`) |

Uses the `browser_worker`'s persistent Chromium session. After solving a CAPTCHA once via noVNC, subsequent calls reuse the session.

## Deployment

- Working directory inside LXC: `/opt/searcher/searcher`
- Env file: `/opt/searcher/.env` (shared with all services)
- Service: `searcher.service`
- Port: `8000`
- Swagger docs: `http://<lxc-ip>:8000/docs`

To update a live deployment:
```bash
pct exec <vmid> -- bash /opt/searcher/deploy/update.sh
```

## Local Testing

```bash
cd searcher
set -a && source ../.env.dev && set +a
../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Docs: `http://127.0.0.1:8000/docs`

Syntax check:
```bash
../.venv/bin/python -m py_compile app.py api/*.py api/services/*.py
```

## Environment Variables

All keys are shared via the root `.env.example`. Provider keys:

- `SEMANTIC_SCHOLAR_API_KEY` (optional — unauthenticated access is rate-limited)
- `OPENALEX_API_KEY` (optional — unauthenticated access is allowed; key raises rate limits)
- `IEEE_XPLORE_API_KEY` (required for IEEE Xplore endpoints)
- `WEB_OF_SCIENCE_API_KEY` (required for Web of Science endpoints)
- `ELSEVIER_API_KEY` (required for Scopus endpoints)

Runtime tuning:

- `REQUEST_TIMEOUT_SECONDS` (default `20`)
- `PDF_MAX_MB` (default `50`)
- `DOWNLOAD_DIR` (default: `downloads/` at repo root)
- `USER_AGENT`

## Search Provider Notes

- `search_semantic_scholar` — unauthenticated access is rate-limited to ~1 request/second; set `SEMANTIC_SCHOLAR_API_KEY` for higher limits.
- `search_openalex` — free, no key required; set `OPENALEX_API_KEY` for higher rate limits. Returns abstracts for all results. Supports `is_oa` and `work_type` filters.
- `search_ieeexplore` — requires `IEEE_XPLORE_API_KEY`; supports Boolean operators (AND, OR, NOT), author filter, content type, sort, and open-access filter.
- `search_scopus` — requires `ELSEVIER_API_KEY`; filter by subject area with `subj` (e.g. `ENGI`, `COMP`).
- `search_sciencedirect` — requires `ELSEVIER_API_KEY`.
- `search_web_of_science` and `search_ebsco` — browser-based; require an active institutional browser session in the persistent Chromium instance.

## Testing Scripts

```bash
./testing/test_health.sh
./testing/test_smoke.sh
./testing/test_api_keys.sh
./testing/test_local_deploy.sh
```

## Example Requests

```bash
curl "http://127.0.0.1:8000/search_semantic_scholar?query=llm+agents&limit=10"
curl "http://127.0.0.1:8000/search_ieeexplore?query=llm+agents&limit=25"
curl "http://127.0.0.1:8000/search_ieeexplore?query=uav+trajectory&year_low=2020&open_access=true"
curl "http://127.0.0.1:8000/search_scopus?query=aviation+noise&limit=50&subj=ENGI"
curl "http://127.0.0.1:8000/search_sciencedirect?query=llm+agents&limit=20"
curl "http://127.0.0.1:8000/search_ebsco?query=uav+manet&limit=100&year_low=2020"
curl "http://127.0.0.1:8000/search_google_scholar_browser?query=uav+manet&limit=200&year_low=2020"
curl "http://127.0.0.1:8000/search_web_of_science?query=llm+agents&limit=10"
curl "http://127.0.0.1:8000/fetch_page?url=https://example.com"
curl "http://127.0.0.1:8000/review_page?url=https://example.com"
curl "http://127.0.0.1:8000/download_pdf?url=https://arxiv.org/pdf/1706.03762.pdf"
```
