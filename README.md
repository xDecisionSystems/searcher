# Searcher MCP (FastAPI)

FastAPI service for:

- Web search (`/search_web`)
- Direct Google search (`/search_google`)
- Webpage fetch + review-ready extraction (`/fetch_page`)
- Website review output (`/review_page`)
- Scholar search (`/search_scholar`)
- Direct Google Scholar search (`/search_google_scholar`)
- PDF download (`/download_pdf`)

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add API keys you want to use.

## 2. Run

```bash
source .venv/bin/activate
set -a && source .env && set +a
uvicorn app:app --host 0.0.0.0 --port 8000
```

Swagger docs:

- `http://<lxc-ip>:8000/docs`

## 2b. Optional systemd (Proxmox LXC)

```bash
mkdir -p /opt/searcher_mcp
cp -r . /opt/searcher_mcp
python3 -m venv /opt/searcher_mcp/.venv
/opt/searcher_mcp/.venv/bin/pip install -r /opt/searcher_mcp/requirements.txt
cp /opt/searcher_mcp/.env.example /opt/searcher_mcp/.env
cp /opt/searcher_mcp/deploy/searcher-mcp.service /etc/systemd/system/searcher-mcp.service
systemctl daemon-reload
systemctl enable --now searcher-mcp
systemctl status searcher-mcp
```

## 3. Endpoints

### `GET /health`

Simple health check.

### `GET /search_web`

Params:

- `query` (required)
- `limit` (default `5`, max `20`)
- `provider` (`auto|serpapi_google|brave|bing|duckduckgo`)

`auto` chooses `serpapi_google`, then `brave`, then `bing`, then `duckduckgo`.

### `GET /search_google`

Params:

- `query` (required)
- `limit` (default `5`, max `20`)

Always uses SerpAPI Google search (`SERPAPI_API_KEY` required).

### `GET /fetch_page`

Params:

- `url` (required, must be `http(s)`)
- `include_html` (default `false`)
- `max_chars` (default `12000`)

Returns title, meta description, cleaned text, and up to 25 links.

### `GET /review_page`

Params:

- `url` (required, must be `http(s)`)
- `include_html` (default `false`)
- `max_chars` (default `12000`)

Returns everything from `/fetch_page` plus headings, word count, and estimated read time.

### `GET /search_scholar`

Params:

- `query` (required)
- `limit` (default `5`, max `20`)
- `provider` (`auto|semantic_scholar|google_scholar_serpapi`)

`auto` uses Semantic Scholar.

### `GET /search_google_scholar`

Params:

- `query` (required)
- `limit` (default `5`, max `20`)

Always uses SerpAPI Google Scholar (`SERPAPI_API_KEY` required).

### `GET /download_pdf`

Params:

- `url` (required)

Downloads PDF to `DOWNLOAD_DIR` (or `/tmp` by default), enforces max size (`PDF_MAX_MB`), and returns file path + size.

## 4. Example Requests

```bash
curl "http://127.0.0.1:8000/search_web?query=fastapi+mcp&provider=duckduckgo"
curl "http://127.0.0.1:8000/search_google?query=fastapi+mcp"
curl "http://127.0.0.1:8000/fetch_page?url=https://example.com"
curl "http://127.0.0.1:8000/review_page?url=https://example.com"
curl "http://127.0.0.1:8000/search_scholar?query=llm+agents&provider=semantic_scholar"
curl "http://127.0.0.1:8000/search_google_scholar?query=retrieval+augmented+generation"
curl "http://127.0.0.1:8000/download_pdf?url=https://arxiv.org/pdf/1706.03762.pdf"
```
