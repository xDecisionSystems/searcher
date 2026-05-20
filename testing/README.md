# Testing Scripts

This folder contains shell scripts for local and deployed service testing.

## Scripts

- `testing/test_health.sh`
  - Verifies `/health` responds with `status=ok` and a `version_name`.
- `testing/test_smoke.sh`
  - Runs a broader smoke test against key endpoints.
  - Includes network-dependent checks by default.
- `testing/test_api_keys.sh`
  - Verifies API-key endpoint behavior.
  - Passes for either:
    - expected "key not configured" responses, or
    - successful responses when keys are configured.
- `testing/test_local_deploy.sh`
  - Starts the API locally with `.venv`, runs smoke checks, then stops the server.

## Usage

Run against an already-running service:

```bash
BASE_URL="http://127.0.0.1:8000" ./testing/test_health.sh
BASE_URL="http://127.0.0.1:8000" ./testing/test_smoke.sh
BASE_URL="http://127.0.0.1:8000" ./testing/test_api_keys.sh
```

Skip network-dependent tests:

```bash
SKIP_NETWORK_TESTS=1 BASE_URL="http://127.0.0.1:8000" ./testing/test_smoke.sh
```

Skip API key tests during smoke run:

```bash
RUN_API_KEY_TESTS=0 BASE_URL="http://127.0.0.1:8000" ./testing/test_smoke.sh
```

Start local app and test automatically:

```bash
./testing/test_local_deploy.sh
```
