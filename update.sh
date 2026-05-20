#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/searcher_mcp"
SERVICE_NAME="searcher-mcp"
SERVICE_FILE="${SERVICE_NAME}.service"
BASE_URL="${SEARCHER_MCP_BASE_URL:-https://raw.githubusercontent.com/xDecisionSystems/searcher_MCP/main}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run update.sh as root (or with sudo)."
  exit 1
fi

mkdir -p "${APP_DIR}/deploy"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

download_file() {
  local src="$1"
  local dst="$2"
  wget -qO "${dst}" "${BASE_URL}/${src}"
}

read_version_name() {
  local version_file="$1"
  if [[ ! -f "${version_file}" ]]; then
    echo "unknown"
    return
  fi
  local version_name
  version_name="$(grep -E '^VERSION_NAME=' "${version_file}" | head -n1 | cut -d'=' -f2- || true)"
  version_name="${version_name%\"}"
  version_name="${version_name#\"}"
  version_name="${version_name%\'}"
  version_name="${version_name#\'}"
  if [[ -z "${version_name}" ]]; then
    echo "unknown"
  else
    echo "${version_name}"
  fi
}

echo "[1/6] Downloading latest service files..."
download_file "app.py" "${TMP_DIR}/app.py"
download_file "requirements.txt" "${TMP_DIR}/requirements.txt"
download_file ".env.example" "${TMP_DIR}/.env.example"
download_file "VERSION.md" "${TMP_DIR}/VERSION.md"
download_file "deploy/${SERVICE_FILE}" "${TMP_DIR}/${SERVICE_FILE}"
download_file "install.sh" "${TMP_DIR}/install.sh"
download_file "update.sh" "${TMP_DIR}/update.sh"

CURRENT_VERSION_NAME="$(read_version_name "${APP_DIR}/VERSION.md")"
NEW_VERSION_NAME="$(read_version_name "${TMP_DIR}/VERSION.md")"
echo "Current version: ${CURRENT_VERSION_NAME}"
echo "New version:     ${NEW_VERSION_NAME}"
read -r -p "Proceed with update? [Y/n] " CONFIRM_UPDATE
CONFIRM_UPDATE="${CONFIRM_UPDATE:-Y}"
case "${CONFIRM_UPDATE}" in
  [Yy]|[Yy][Ee][Ss]) ;;
  [Nn]|[Nn][Oo])
    echo "Update canceled by user."
    exit 0
    ;;
  *)
    echo "Unrecognized response. Defaulting to Yes."
    ;;
esac

echo "[2/6] Updating local files..."
install -m 0644 "${TMP_DIR}/app.py" "${APP_DIR}/app.py"
install -m 0644 "${TMP_DIR}/requirements.txt" "${APP_DIR}/requirements.txt"
install -m 0644 "${TMP_DIR}/.env.example" "${APP_DIR}/.env.example"
install -m 0644 "${TMP_DIR}/VERSION.md" "${APP_DIR}/VERSION.md"
install -m 0644 "${TMP_DIR}/${SERVICE_FILE}" "${APP_DIR}/deploy/${SERVICE_FILE}"
install -m 0755 "${TMP_DIR}/install.sh" "${APP_DIR}/install.sh"
install -m 0755 "${TMP_DIR}/update.sh" "${APP_DIR}/update.sh"

echo "[3/6] Ensuring virtual environment exists..."
if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
  python3 -m venv "${APP_DIR}/.venv"
fi

echo "[4/6] Installing/updating Python dependencies..."
"${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/.venv/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"

echo "[5/6] Refreshing systemd unit..."
cp "${APP_DIR}/deploy/${SERVICE_FILE}" "/etc/systemd/system/${SERVICE_FILE}"
systemctl daemon-reload

echo "[6/6] Restarting service..."
systemctl restart "${SERVICE_NAME}"
systemctl --no-pager --full status "${SERVICE_NAME}" || true

echo
echo "Update complete."
echo "Base URL used: ${BASE_URL}"
