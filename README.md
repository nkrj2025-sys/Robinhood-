# Robinhood Trading

Python examples for calling the Robinhood Crypto Trading API from an agent or
local shell.

## Files

- `robinhood-api-trading/robinhood_api_trading.py` - original v1 client sample.
- `robinhood-api-trading/robinhood_api_trading_v2.py` - v2 client with a
  dry-run-first order workflow.

## Credentials

The scripts read credentials from environment variables:

```bash
export ROBINHOOD_API_KEY="your-api-key"
export ROBINHOOD_BASE64_PRIVATE_KEY="base64-ed25519-private-key-seed"
```

Do not commit real keys to the repository. In Cursor Cloud, store them as
Secrets or environment variables.

## How an agent places a crypto order

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
