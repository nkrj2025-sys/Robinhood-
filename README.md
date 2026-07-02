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

An agent should never submit a live order from an ambiguous prompt. Use this flow:

1. Collect the exact account, symbol or trading pair, side, order type, and size.
2. Preview the order and fetch a quote or estimated price.
3. Present the preview, alerts, fees, and quote details to the user.
4. Require explicit user confirmation for the exact order.
5. Submit once with an idempotency key.
6. Fetch the order after submission to verify its state.

For the Cursor Robinhood MCP server, equity and option orders follow the same
pattern: call `review_equity_order` or `review_option_order` first, then call
`place_equity_order` or `place_option_order` only after explicit confirmation.

This repository's `robinhood_api_trading_v2.py` script demonstrates the crypto
REST API path. It previews by default and will not place a live order unless all
live-order gates are present.

Dry-run BTC estimate:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --asset-quantity 0.000001
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

The script also accepts `--client-order-id` if you need to retry the same logical
order with the same idempotency key.
