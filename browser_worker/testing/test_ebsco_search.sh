#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8010}"
QUERY="${QUERY:-UAV trajectories}"
LIMIT="${LIMIT:-5}"
YEAR_LOW="${YEAR_LOW:-2020}"
YEAR_HIGH="${YEAR_HIGH:-2025}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

RESPONSE_STATUS=""
RESPONSE_BODY=""

call_get() {
  local path="$1"
  local label="$2"
  local out_file="${TMP_DIR}/response.json"
  if ! RESPONSE_STATUS="$(curl -sS -o "${out_file}" -w "%{http_code}" "${BASE_URL}${path}")"; then
    echo "FAIL: ${label} request failed"
    exit 1
  fi
  RESPONSE_BODY="$(cat "${out_file}")"
}

assert_body_contains() {
  local pattern="$1"
  local label="$2"
  if ! grep -Eq "${pattern}" <<<"${RESPONSE_BODY}"; then
    echo "FAIL: ${label} response missing expected pattern: ${pattern}"
    echo "Body (first 500 chars): ${RESPONSE_BODY:0:500}"
    exit 1
  fi
}

ENCODED_QUERY="$(python3 -c "import urllib.parse; print(urllib.parse.quote('${QUERY}'))")"

echo "Running EBSCO browser search test against: ${BASE_URL}"
echo "Query: ${QUERY}, limit: ${LIMIT}, years: ${YEAR_LOW}-${YEAR_HIGH}"

call_get "/search_ebsco?query=${ENCODED_QUERY}&limit=${LIMIT}&year_low=${YEAR_LOW}&year_high=${YEAR_HIGH}" "search_ebsco"

if [[ "${RESPONSE_STATUS}" == "200" ]]; then
  assert_body_contains '"page_count"' "search_ebsco"
  assert_body_contains '"pages_html"' "search_ebsco"
  PAGE_COUNT="$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('page_count',0))" "${RESPONSE_BODY}")"
  echo "PASS: search_ebsco returned ${PAGE_COUNT} HTML snapshot(s)"
else
  echo "FAIL: search_ebsco returned HTTP ${RESPONSE_STATUS}"
  echo "Body: ${RESPONSE_BODY:0:500}"
  exit 1
fi
