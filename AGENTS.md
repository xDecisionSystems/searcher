# AGENTS.md

Guidance for programming agents contributing to this repository.

## 1. Mission

Maintain two FastAPI services and a browser stack deployed together as a single stack:

- `searcher/` — scholarly search, web page retrieval, and PDF download via HTTP APIs.
- `browser_worker/` — browser-driven paper download for authenticated publisher portals.

Prioritize correctness, safe defaults, and predictable API behavior.

## 2. Repository Scope

```
searcher/
├── searcher/                        # Search API service
│   ├── app.py                       # Entrypoint
│   ├── api/                         # API routes and business logic
│   │   ├── api.py
│   │   ├── config.py
│   │   ├── http_client.py
│   │   ├── utils.py
│   │   └── services/
│   │       ├── page.py
│   │       ├── pdf.py
│   │       └── search.py
│   ├── requirements.txt
│   ├── deploy/searcher.service
│   ├── testing/
│   ├── README.md
│   └── ARCHITECTURE.md
├── browser_worker/                  # Browser-automation download service
│   ├── app.py
│   ├── browser_worker/
│   │   ├── api.py
│   │   ├── config.py
│   │   ├── logger.py
│   │   └── services/
│   │       ├── download.py          # Core download logic, lock, no_access detection
│   │       └── recorder.py          # Session recording and strategy persistence
│   │   └── strategies/              # Per-domain download strategy JSON files
│   ├── requirements.txt
│   ├── deploy/
│   │   ├── browser-worker.service
│   │   └── chromium-cdp.service
│   └── README.md
├── deploy/                          # Stack-level deployment scripts
│   ├── update.sh                    # Updates code and restarts in the LXC
│   └── restart.sh                   # Restarts all services in dependency order
├── exploration/                     # Standalone evaluation scripts (not production)
├── .env.example                     # Shared env template for all services
├── VERSION.md                       # Stack version (single file at repo root)
├── AGENTS.md
├── CLAUDE.md
└── README.md
```

If you add or change behavior in a service, update that service's `README.md` and the root `.env.example` in the same change.

## 3. Downloads Folder

- The repo contains a `downloads/` folder at the root for all test and API-triggered file downloads.
- All files inside `downloads/` are git-ignored; only the folder itself (via its internal `.gitignore`) is tracked.
- **When testing any endpoint that downloads a file** (e.g. `/download_pdf`, `/download_ebsco_paper`, `browser_worker` download endpoints), always set `DOWNLOAD_DIR` to point at `<repo_root>/downloads/` — or rely on the default, which already resolves there.
- Do not scatter downloaded files into the system temp dir or other locations during testing.

## 4. Deployment Policy

- Production: single Debian-based Proxmox LXC with `systemd`, running two FastAPI services plus browser stack.
- Code is deployed to `/opt/searcher/` inside the LXC (git clone of this repo).
- Shared env lives at `/opt/searcher/.env`; each service symlinks to it.
- Local `.venv` + `uvicorn` is for testing only.
- Use `deploy/update.sh` inside the LXC for code updates — no full redeploy needed.
- Do not run per-service `install.sh` or `update.sh` — these are legacy and unused.

## 5. Agent Roles

- **Implementer agent**: owns code changes inside a service's module (`api/` or `browser_worker/`).
- **Documentation agent**: owns `README.md`, `ARCHITECTURE.md`, root `.env.example`.
- **Verification agent**: runs syntax checks and smoke tests for the affected service.

When using multiple agents in parallel, assign disjoint file ownership.

## 6. Coding Rules

- Python 3.10+ compatible syntax.
- Preserve current API contracts unless explicitly asked to break them.
- Keep endpoints deterministic and JSON-serializable.
- Validate all user inputs (URLs, limits, provider names).
- Fail with explicit HTTP status and message.
- Keep network calls bounded with timeouts.
- Never log or expose API keys or secrets.
- Keep external dependencies minimal.
- For standalone scripts, prefer flat top-level execution flow and do not add `main()`.

## 7. Python Environment Rules (Required)

- Shared `.venv` at repo root for local development.
- Install service deps: `.venv/bin/python -m pip install -r <service>/requirements.txt`
- Re-run whenever a service's `requirements.txt` changes.
- Do not use system/global `python`, `python3`, or `pip` for project tasks.
- Use `.env.dev` at the repo root for local development; `.env` is the production file inside the LXC.

## 8. Version Update Rule

- Whenever code changes are made, automatically increment the patch version in `VERSION.md` at the repo root (e.g. `v1.0.4` → `v1.0.5`).
- If the user says `update version name to <new>`, use that exact name instead.
- Format: `VERSION_NAME=<version name>`

## 9. Safety and Security

- Accept only `http`/`https` URLs.
- Treat downloaded content as untrusted.
- Enforce PDF size limits during streaming downloads.
- Reject obviously incorrect content types where possible.
- Do not execute downloaded files.
- `browser_worker/` can navigate arbitrary URLs — restrict port 9222 by firewall if needed.

## 10. Change Workflow

1. Identify which service is affected (`searcher/` or `browser_worker/`).
2. Read that service's `README.md` and main module files.
3. Implement the smallest coherent change.
4. Run syntax checks for the affected service.
5. Update that service's docs and the root `.env.example` if config keys changed.
6. **API reference page:** whenever an endpoint is added, removed, or its parameters change, update `searcher/api/static/api_reference.html` in the same change. This file is served live at `/api-reference` and is the authoritative reference for AI agents.
7. Summarize changes, assumptions, and residual risks.

## 11. Domain Strategy Generation Protocol (Required)

When asked to create or update a `browser_worker` strategy for a publisher/domain:

Interpretation rule:
- Any request phrased like `Generate strategy <domain>`, `Generate strategy for <website>`, or equivalent means:
  1) start a recorded browser session,
  2) perform/process the recording,
  3) produce/update `browser_worker/browser_worker/strategies/<domain>.json`.
- Do not satisfy this request by hand-authoring a strategy without a recording, unless the user explicitly asks for a manual fallback.

1. Do not start by hand-writing JSON.
2. Use the hosted stack at `searcher.xds-lab.com` to record a real interaction first.
3. Call the browser worker endpoint for recording:
   - `POST https://searcher.xds-lab.com/aev/browser/record_session?url=<paper-url>&timeout_seconds=60`
4. Perform the download flow in the remote browser session (login if needed), then stop recording:
   - `POST https://searcher.xds-lab.com/aev/browser/stop_recording`
5. Retrieve and inspect the generated strategy:
   - `GET https://searcher.xds-lab.com/aev/browser/strategies/<domain>`
6. Validate replay with a fresh paper URL from the same domain using:
   - `POST https://searcher.xds-lab.com/aev/browser/download_paper`
7. Only after successful replay, persist/update `browser_worker/browser_worker/strategies/<domain>.json` in this repo.

Notes:
- MCP endpoint for agent tooling: `https://searcher.xds-lab.com/aev/browser/mcp`
- Search MCP endpoint: `https://searcher.xds-lab.com/aev/search/mcp`
- If institutional access is unavailable, store an explicit inaccessible strategy (`accessible: false`) with a clear `inaccessible_reason` instead of fake click steps.

## 12. Definition of Done

- Code is syntactically valid.
- Endpoint behavior matches documentation.
- New config keys are documented in the root `.env.example`.
- Existing functionality remains intact unless explicitly changed.
- Risks and follow-ups are stated.
