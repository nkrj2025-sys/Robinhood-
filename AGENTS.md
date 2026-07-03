# Robinhood Trading

## Cursor Cloud specific instructions

### Overview
This repo contains a Python client for the Robinhood Crypto Trading API. There are
two runnable scripts in `robinhood-api-trading/`:
- `robinhood_api_trading.py` (v1 client, `/api/v1/...` endpoints)
- `robinhood_api_trading_v2.py` (v2 client, `/api/v2/...` endpoints, pagination, safer `main()`)

Both sign requests with Ed25519 keys (`pynacl`) and call the REST API via `requests`.

### Runtime / commands
- Use `python3` (there is no `python` on PATH).
- Dependencies: `requests`, `pynacl` (see `robinhood-api-trading/requirements.txt`).
  These are installed by the update script; no manual install needed at session start.
- Run v1: `python3 robinhood-api-trading/robinhood_api_trading.py`
- Run v2 (dry-run by default): `python3 robinhood-api-trading/robinhood_api_trading_v2.py`
  - v2 requires both env vars to be set (raises `ValueError` otherwise)
  - Only places a live order when `ROBINHOOD_PLACE_REAL_ORDER=true`
  - Supports full CLI: `--symbol`, `--side`, `--order-type`, `--asset-quantity`, `--place`, `--confirm-live-order "PLACE LIVE ORDER"`
- Syntax validation: `python3 -m py_compile robinhood-api-trading/*.py`

### Credentials (non-obvious)
- `robinhood_api_trading.py` reads credentials from environment variables:
  `ROBINHOOD_API_KEY` and `ROBINHOOD_BASE64_PRIVATE_KEY` (base64-encoded Ed25519 seed).
  Falls back to literal placeholder strings if unset; `main()` fails at `base64.b64decode(...)`.
  **Do NOT hardcode real keys into the file** (it gets committed) — set them as Secrets/env vars instead.

### Docker (non-obvious, important)
- Docker CE + Compose plugin are installed at the **system level** (captured in VM snapshot).
  They are **NOT** part of the update script. The repo itself does not use Docker; it's available as a general dev tool.
- The daemon is **NOT auto-started** (there is no systemd/service manager in the VM).
  Start it manually and leave it running in a background/tmux session:
  ```bash
  sudo dockerd > /tmp/dockerd.log 2>&1 &
  ```
- **DinD workarounds** are already configured:
  - `storage-driver: fuse-overlayfs` in `/etc/docker/daemon.json`
  - `iptables`/`ip6tables` set to `-legacy` (container port publishing/NAT fails otherwise)
  - If Docker 29+ is ever installed, also disable `containerd-snapshotter` to keep fuse-overlayfs working
- The `ubuntu` user is in the `docker` group, but that membership is not active in an already-open shell.
  Use `sudo docker ...` in the current session (or fresh login).

### Network egress (non-obvious, important)
- The live API host `trading.robinhood.com` **IS reachable** from the Cloud Agent VM.
  A signed request reaches the real API:
  - Invalid/ephemeral key → HTTP `401` ("An API credential matching the passed in api key was not found")
  - Unsigned request → HTTP `400` ("Request missing required headers")
- The full code path (key load → request signing → HTTPS call → API validation) can be verified
  without real credentials by generating an ephemeral `SigningKey` and confirming the API responds
  with a `401`; only a *successful authenticated* response requires valid `ROBINHOOD_API_KEY` /
  `ROBINHOOD_BASE64_PRIVATE_KEY` secrets.
