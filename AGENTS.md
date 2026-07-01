# Robinhood Trading

## Cursor Cloud specific instructions

### Overview
This repo contains a Python client for the Robinhood Crypto Trading API. The main
script is `robinhood-api-trading/robinhood_api_trading.py` (a second file,
`robinhood_api_trading_v2.py`, is currently a placeholder). It signs requests with
an Ed25519 key (`pynacl`) and calls the REST API via `requests`.

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
- The live API host `trading.robinhood.com` is NOT reachable by default from the
  Cloud Agent VM (requests fail with `Connection reset by peer`). A real
  authenticated call requires this domain to be added to the network allowlist.
- The full local code path (key load → request signing → HTTPS call) can be
  verified without real credentials by generating an ephemeral `SigningKey` and
  confirming the signed request is built; only the outbound call to Robinhood is
  gated by egress.
