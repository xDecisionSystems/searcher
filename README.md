# searcher_MCP

Monorepo containing four services deployed together in a single Proxmox LXC.

## Services

### [`searcher/`](searcher/)

FastAPI service for scholarly search and web content retrieval.

- Scholar search via Semantic Scholar, Google Scholar (SerpAPI), IEEE Xplore, Web of Science, and Elsevier Scopus
- Web page fetch and review-ready extraction
- Direct PDF download with size and content-type enforcement

### [`browser_worker/`](browser_worker/)

FastAPI service that drives a persistent Chromium browser to download papers from authenticated publisher portals.

- Log in once via Chromium CDP — session persists across restarts
- Accepts paper page URLs, navigates to the PDF, downloads it to disk
- Intended for pages that require institutional login (e.g. ScienceDirect, IEEE)

## Repository Layout

```
searcher_MCP/
├── searcher/               # Scholar search FastAPI service
├── browser_worker/         # Browser-automation download FastAPI service
├── deploy/                 # Deployment and operations scripts
│   ├── proxmox_deploy.sh   # Creates LXC and deploys all services
│   ├── update.sh           # Updates code and restarts services in the LXC
│   └── restart.sh          # Restarts all services in dependency order
├── exploration/            # Standalone scripts for evaluating integration options
├── .env.example            # Shared env template covering all services
├── VERSION.md              # Stack version
├── AGENTS.md               # Agent and contributor instructions
├── CLAUDE.md               # Claude Code instructions
└── README.md               # This file
```

## Deployment Overview

All three services run in a single Proxmox LXC.

| Service | Port | Description |
|---------|------|-------------|
| `searcher-mcp` | 8000 | Scholar search FastAPI |
| `browser-worker` | 8010 | Browser-download FastAPI |
| `novnc` | 6080 | Browser-based remote desktop (password protected) |
| `chromium-display` | 9222 (localhost) | Chromium with GUI on virtual display |
| `x11vnc` | 5900 (localhost) | VNC server on virtual display |
| `xvfb` | — | Virtual display :99 |

Deployed code lives at `/opt/repo/` inside the LXC (a git clone of this repo).
A single shared `/opt/repo/.env` covers all services — symlinked from each service directory.

### Using as an MCP server with Claude Code

The searcher service exposes all its tools as an MCP server at `/mcp`.

Add to your Claude Code MCP settings (`~/.claude/settings.json` or via `/config`):

```json
{
  "mcpServers": {
    "searcher": {
      "type": "http",
      "url": "https://searcher.xds-lab.com/mcp"
    }
  }
}
```

A ready-to-use config file is at [mcp_config.json](mcp_config.json) — update the IP then run:

```bash
claude mcp add --config mcp_config.json
```

Available MCP tools mirror the API endpoints: `search_scholar`, `search_google_scholar`, `search_ieeexplore`, `search_web_of_science`, `search_scopus`, `fetch_page`, `review_page`, `download_pdf`.

---

### Quick deploy

```bash
./deploy/proxmox_deploy.sh
```

### Update existing deployment

```bash
pct exec <vmid> -- bash /opt/repo/deploy/update.sh
```

### Restart all services

```bash
pct exec <vmid> -- bash /opt/repo/deploy/restart.sh
```

### Log into publisher portals (ScienceDirect, IEEE, etc.)

1. Open `http://<lxc-ip>:6080/vnc.html` in your browser
2. Enter your `VNC_PASSWORD`
3. A full Chromium browser appears — log in to the portal normally
4. Session is saved to `/opt/repo/browser_worker/chromium-profile` — persists across restarts
