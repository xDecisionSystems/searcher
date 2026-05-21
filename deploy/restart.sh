#!/usr/bin/env bash
# restart.sh
#
# Restarts all searcher-stack services in dependency order.
# Must be run as root inside the LXC.
#
# Usage:
#   ./deploy/restart.sh            # restart all
#   ./deploy/restart.sh --status   # show service status only

set -euo pipefail

CDP_PORT=9222
NOVNC_PORT=6080
WORKER_PORT=8010
SEARCHER_PORT=8000

STATUS_ONLY=0
[[ "${1:-}" == "--status" ]] && STATUS_ONLY=1

log()  { echo "[restart] $*"; }
pass() { echo "[restart] OK: $*"; }
fail() { echo "[restart] FAIL: $*" >&2; exit 1; }

SERVICES=(xvfb x11vnc chromium-display novnc browser-worker searcher-mcp)

if [[ "$STATUS_ONLY" == "1" ]]; then
  echo "Service status:"
  for svc in "${SERVICES[@]}"; do
    status="$(systemctl is-active "$svc" 2>/dev/null || echo inactive)"
    echo "  ${svc}: ${status}"
  done
  exit 0
fi

# Display stack must come up before browser services
log "Restarting xvfb ..."
systemctl restart xvfb
sleep 2

log "Restarting x11vnc ..."
systemctl restart x11vnc
sleep 1

log "Restarting chromium-display ..."
systemctl restart chromium-display
for i in $(seq 1 15); do
  curl -sf "http://127.0.0.1:${CDP_PORT}/json/version" > /dev/null 2>&1 && break
  [[ "$i" == "15" ]] && fail "chromium-display did not come up"
  sleep 2
done
pass "chromium-display"

log "Restarting novnc ..."
systemctl restart novnc
for i in $(seq 1 10); do
  curl -sf "http://127.0.0.1:${NOVNC_PORT}/" > /dev/null 2>&1 && break
  [[ "$i" == "10" ]] && fail "novnc did not come up"
  sleep 2
done
pass "novnc"

log "Restarting browser-worker ..."
systemctl restart browser-worker
for i in $(seq 1 10); do
  curl -sf "http://127.0.0.1:${WORKER_PORT}/health" > /dev/null 2>&1 && break
  [[ "$i" == "10" ]] && fail "browser-worker did not pass health check"
  sleep 2
done
pass "browser-worker"

log "Restarting searcher-mcp ..."
systemctl restart searcher-mcp
for i in $(seq 1 10); do
  curl -sf "http://127.0.0.1:${SEARCHER_PORT}/health" > /dev/null 2>&1 && break
  [[ "$i" == "10" ]] && fail "searcher-mcp did not pass health check"
  sleep 2
done
pass "searcher-mcp"

echo ""
echo "All services restarted successfully."
echo ""
systemctl is-active "${SERVICES[@]}" 2>/dev/null | paste - - - - - - | \
  awk '{printf "  xvfb:%s  x11vnc:%s  chromium:%s  novnc:%s  browser-worker:%s  searcher-mcp:%s\n",$1,$2,$3,$4,$5,$6}'
