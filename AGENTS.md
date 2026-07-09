# Robinhood Trading

## Cursor Cloud specific instructions

### Overview
This repo contains Python clients for the Robinhood Crypto Trading API. The
legacy example is `robinhood-api-trading/robinhood_api_trading.py`; the safer v2
CLI is `robinhood-api-trading/robinhood_api_trading_v2.py`. Requests are signed
with an Ed25519 key (`pynacl`) and sent to the REST API via `requests`.

### Runtime / commands
- Use `python3` (there is no `python` on PATH).
- Dependencies: `requests`, `pynacl` (see `robinhood-api-trading/requirements.txt`).
  These are installed by the update script; no manual install needed at session start.
- Preview an order: `python3 robinhood-api-trading/robinhood_api_trading_v2.py`.
- Run the legacy app: `python3 robinhood-api-trading/robinhood_api_trading.py`.

### Credentials (non-obvious)
- `robinhood_api_trading.py` reads credentials from environment variables:
  `ROBINHOOD_API_KEY` and `ROBINHOOD_BASE64_PRIVATE_KEY` (base64-encoded Ed25519
  seed). It falls back to literal placeholder strings if unset, in which case
  `main()` fails at `base64.b64decode(...)`.
- `robinhood_api_trading_v2.py` can preview orders without credentials. Live
  submission requires `ROBINHOOD_API_KEY`, `ROBINHOOD_BASE64_PRIVATE_KEY`, and
  either `--place-real-order` or `ROBINHOOD_PLACE_REAL_ORDER=true`.
- Do NOT hardcode real keys into the file (it gets committed) — set them as
  Secrets/env vars instead.

### Network egress (non-obvious, important)
- The live API host `trading.robinhood.com` IS reachable from the Cloud Agent VM.
  A signed request reaches the real API: with an invalid/ephemeral key it returns
  HTTP `401` ("An API credential matching the passed in api key was not found"),
  and an unsigned request returns HTTP `400` ("Request missing required headers").
- The full code path (key load → request signing → HTTPS call → API validation)
  can be verified without real credentials by generating an ephemeral `SigningKey`
  and confirming the API responds with a `401`; only a *successful authenticated*
  response requires valid `ROBINHOOD_API_KEY` / `ROBINHOOD_BASE64_PRIVATE_KEY`.
