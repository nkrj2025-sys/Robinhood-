# Robinhood Trading

## Cursor Cloud specific instructions

### Overview
This repo contains a Python client for the Robinhood Crypto Trading API. There are
two entry points: `robinhood-api-trading/robinhood_api_trading.py` (v1, reads
credentials from module-level env vars at import time) and
`robinhood-api-trading/robinhood_api_trading_v2.py` (v2, a fully-implemented client
that takes credentials via its constructor and gracefully handles non-JSON error
responses). Both sign requests with an Ed25519 key (`pynacl`) and call the REST API
via `requests`.

### Runtime / commands
- Use `python3` (there is no `python` on PATH).
- Dependencies: `requests`, `pynacl` (see `robinhood-api-trading/requirements.txt`).
  These are installed by the update script; no manual install needed at session start.
- Run the app: `python3 robinhood-api-trading/robinhood_api_trading.py` (v1) or
 `python3 robinhood-api-trading/robinhood_api_trading_v2.py` (v2).
- Note: v1 `main()` calls `.json()` on the API response; error responses are
 `text/plain`, so an unauthenticated run prints `None` after logging a JSON-decode
 error (expected). v2 `main()` handles non-JSON responses and raises `RuntimeError`
 on an unauthenticated `401` (expected without valid credentials). v2 also supports
 `ROBINHOOD_PLACE_REAL_ORDER=true` to place a live order — leave it unset for a dry run.

### Credentials (non-obvious)
- `robinhood_api_trading.py` reads credentials from environment variables:
  `ROBINHOOD_API_KEY` and `ROBINHOOD_BASE64_PRIVATE_KEY` (base64-encoded Ed25519
  seed). It falls back to literal placeholder strings if unset, in which case
  `main()` fails at `base64.b64decode(...)`. Do NOT hardcode real keys into the file
  (it gets committed) — set them as Secrets/env vars instead.

### Network egress (non-obvious, important)
- The live API host `trading.robinhood.com` IS reachable from the Cloud Agent VM.
  A signed request reaches the real API: with an invalid/ephemeral key it returns
  HTTP `401` ("An API credential matching the passed in api key was not found"),
  and an unsigned request returns HTTP `400` ("Request missing required headers").
- The full code path (key load → request signing → HTTPS call → API validation)
  can be verified without real credentials by generating an ephemeral `SigningKey`
  and confirming the API responds with a `401`; only a *successful authenticated*
  response requires valid `ROBINHOOD_API_KEY` / `ROBINHOOD_BASE64_PRIVATE_KEY`.
