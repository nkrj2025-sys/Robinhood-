# Robinhood Trading

Python examples for the Robinhood Crypto Trading API.

## Setup

Install dependencies:

```bash
python3 -m pip install -r robinhood-api-trading/requirements.txt
```

Set credentials as environment variables. Do not commit real keys.

```bash
export ROBINHOOD_API_KEY="..."
export ROBINHOOD_BASE64_PRIVATE_KEY="..."
```

## How an agent places an order safely

An agent should never submit a live order from an ambiguous prompt. Use this
flow:

1. Collect the exact account, symbol or trading pair, side, order type, and size.
2. Build and show the order payload in dry-run mode.
3. Preview market data, quote details, fees, alerts, or other pre-trade checks.
4. Require explicit user confirmation for the exact order.
5. Submit once with an idempotency key.
6. Fetch the order after submission to verify its state.

For the Cursor Robinhood MCP server, equity and option orders follow the same
pattern: call `review_equity_order` or `review_option_order` first, present the
review output to the user, then call `place_equity_order` or
`place_option_order` only after explicit confirmation.

This repository's `robinhood_api_trading_v2.py` script demonstrates the crypto
REST API path. It builds a dry-run order preview by default and will not place a
live order unless all live-order gates are present.

Dry-run BTC order payload without credentials:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --asset-quantity 0.000001
```

Dry-run with a signed market-data preview:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --asset-quantity 0.000001 \
  --preview-marketdata
```

Live crypto order, after you have confirmed the exact order details:

```bash
export ROBINHOOD_CRYPTO_ACCOUNT_NUMBER="..."
export ROBINHOOD_PLACE_REAL_ORDER=true

python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --account-number "$ROBINHOOD_CRYPTO_ACCOUNT_NUMBER" \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --asset-quantity 0.000001 \
  --place \
  --confirm-live-order "PLACE LIVE ORDER"
```

The script also accepts `--client-order-id` if you need to retry the same
logical order with the same idempotency key.
