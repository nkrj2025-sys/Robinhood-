# Robinhood Trading

## Cursor Cloud specific instructions

### Overview
This repo contains a Python client for the Robinhood Crypto Trading API. There are
two scripts: `robinhood-api-trading/robinhood_api_trading.py` (v1) and
`robinhood-api-trading/robinhood_api_trading_v2.py` (v2, a session-based client that
hits the `/api/v2/...` endpoints and includes a small demo `main()`). Both sign
requests with an Ed25519 key (`pynacl`) and call the REST API via `requests`.

### Runtime / commands
- Use `python3` (there is no `python` on PATH).
- Dependencies: `requests`, `pynacl` (see `robinhood-api-trading/requirements.txt`).
  These are installed by the update script; no manual install needed at session start.
- Run the app: `python3 robinhood-api-trading/robinhood_api_trading.py`.

### Credentials (non-obvious)
- `robinhood_api_trading.py` reads credentials from environment variables:
  `ROBINHOOD_API_KEY` and `ROBINHOOD_BASE64_PRIVATE_KEY` (base64-encoded Ed25519
  seed). It falls back to literal placeholder strings if unset, in which case
  `main()` fails at `base64.b64decode(...)`. Do NOT hardcode real keys into the file
  (it gets committed) — set them as Secrets/env vars instead.

### Network egress (non-obvious, important)
- Reaching the live API host `trading.robinhood.com` depends on the VM's egress
 allowlist. It has been reachable in some sessions, but in others every TCP
 connection is reset ("Connection reset by peer" / curl error 35). If you see this,
 the domain likely needs to be added to the Cloud Agent network allowlist — it is
 an egress restriction, not a code bug.
- When the host IS reachable, a signed request reaches the real API: with an
 invalid/ephemeral key it returns HTTP `401` ("An API credential matching the
 passed in api key was not found"), and an unsigned request returns HTTP `400`
 ("Request missing required headers").
- The offline part of the code path (key load → request signing) can always be
 verified without network access: instantiate the client with the injected
 secrets and confirm `get_authorization_header(...)` produces an `x-signature`
 that validates against `client.private_key.verify_key`. Only the *live HTTPS
 call* requires egress to `trading.robinhood.com`, and only a *successful
 authenticated* response requires valid `ROBINHOOD_API_KEY` /
 `ROBINHOOD_BASE64_PRIVATE_KEY`.
