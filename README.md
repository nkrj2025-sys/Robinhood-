# Robinhood Trading

Python clients and command-line helpers for calling the Robinhood Crypto
Trading API from an agent or local shell.

## Files

- `robinhood-api-trading/robinhood_api_trading.py` - primary CLI for account
  connection checks, market data, holdings, order listing, guarded order
  placement, and guarded cancellation.
- `robinhood-api-trading/robinhood_api_trading_v2.py` - v2 market-order helper
  with a dry-run-first workflow and optional market checks.
- `tests/test_robinhood_api_trading_v2.py` - focused tests for the v2 order
  helpers and live-order gate.

## Setup

Install runtime dependencies before using signed Robinhood API requests:

```bash
python3 -m pip install -r robinhood-api-trading/requirements.txt
```

## Credentials

Create API credentials in Robinhood, then provide them through environment
variables. Do not hardcode real keys in this repository.

```bash
export ROBINHOOD_API_KEY="your-api-key"
export ROBINHOOD_BASE64_PRIVATE_KEY="your-base64-ed25519-private-key-seed"
```

In Cursor Cloud, store credentials as Secrets or environment variables.

## Primary CLI

### Connect to the account

Validate the credentials and fetch the crypto trading accounts:

```bash
python3 robinhood-api-trading/robinhood_api_trading.py connect
```

The command masks account numbers in its output.

### Market data

```bash
python3 robinhood-api-trading/robinhood_api_trading.py quote BTC-USD
python3 robinhood-api-trading/robinhood_api_trading.py estimate BTC-USD --side both --quantity 0.0001
python3 robinhood-api-trading/robinhood_api_trading.py holdings --asset-code BTC
```

### Orders

Order commands dry-run by default and print the payload that would be sent:

```bash
python3 robinhood-api-trading/robinhood_api_trading.py order \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --asset-quantity 0.0001
```

To place a live order, both safeguards must be present:

```bash
ROBINHOOD_PLACE_REAL_ORDER=true \
python3 robinhood-api-trading/robinhood_api_trading.py order \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --asset-quantity 0.0001 \
  --confirm-live-trade
```

Canceling an order also requires `ROBINHOOD_PLACE_REAL_ORDER=true` and
`--confirm-live-trade`.

## V2 market-order helper

### How an agent places a crypto order

The v2 script is intentionally guarded so an agent can show the order it would
place before it sends anything to Robinhood.

1. Build a market-order payload with:
   - `client_order_id` - UUID for idempotency and tracking.
   - `side` - `buy` or `sell`.
   - `type` - `market`.
   - `symbol` - trading pair such as `BTC-USD`.
   - `market_order_config` - either `asset_quantity` or `quote_amount`.
2. Sign the request with the Ed25519 private key from
   `ROBINHOOD_BASE64_PRIVATE_KEY`.
3. Optionally resolve the crypto account number and fetch trading-pair and
   estimated-price data with `--check-market`.
4. Submit `POST /api/v2/crypto/trading/orders/?account_number=...` only when
   both live-order confirmations are present.

## Dry-run preview

Run this with no credentials to preview the exact order body only:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --asset-quantity 0.000001
```

This command stays offline even when credentials are present.

Use `--quote-amount` instead of `--asset-quantity` to size the order by USD:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --quote-amount 5
```

## Live order submission

With credentials set, add `--check-market` to fetch the account, trading pair,
and estimated price without placing an order:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --asset-quantity 0.000001 \
  --check-market
```

Live orders require two confirmations:

```bash
export ROBINHOOD_PLACE_REAL_ORDER=true
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --asset-quantity 0.000001 \
  --place-real-order
```

If either `ROBINHOOD_PLACE_REAL_ORDER=true` or `--place-real-order` is missing,
the script remains in dry-run mode.

## MCP note

This repository also contains `.cursor/mcp.json` for a local Postgres MCP server.
That server is unrelated to Robinhood order placement. If an agent is using
Robinhood brokerage MCP tools, use review tools before place tools and require
explicit user confirmation before any live trade.
