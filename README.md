# Robinhood Trading

Python examples for the Robinhood Crypto Trading API.

## Setup

Use `python3` and install the package requirements:

```bash
python3 -m pip install -r robinhood-api-trading/requirements.txt
```

Set credentials as environment variables. Do not commit real keys.

```bash
export ROBINHOOD_API_KEY="..."
export ROBINHOOD_BASE64_PRIVATE_KEY="..."
```

The private key must be a base64-encoded Ed25519 seed.

## How an agent places a crypto order

`robinhood-api-trading/robinhood_api_trading_v2.py` is the safer runner for
agent-driven order placement. By default it does not submit an order. It:

1. Loads credentials from the environment.
2. Fetches the first crypto trading account.
3. Loads the requested trading pair.
4. Prints an estimated price when `asset_quantity` is present.
5. Prints the order that would be placed.
6. Places the order only when `ROBINHOOD_PLACE_REAL_ORDER=true`.

Dry run:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py
```

Live order opt-in:

```bash
export ROBINHOOD_ORDER_SYMBOL="BTC-USD"
export ROBINHOOD_ORDER_SIDE="buy"
export ROBINHOOD_ORDER_TYPE="market"
export ROBINHOOD_ORDER_ASSET_QUANTITY="0.000001"
export ROBINHOOD_PLACE_REAL_ORDER="true"
python3 robinhood-api-trading/robinhood_api_trading_v2.py
```

For advanced order configs, provide the exact API config object as JSON:

```bash
export ROBINHOOD_ORDER_TYPE="limit"
export ROBINHOOD_ORDER_CONFIG_JSON='{"asset_quantity":"0.000001","limit_price":"50000.00"}'
```

The script sends this as `<order_type>_order_config`, generates a fresh
`client_order_id`, signs the request with the Ed25519 private key, and posts to
Robinhood's crypto trading orders endpoint.

## Equity and options orders through the Robinhood MCP

When an agent has access to the Robinhood MCP tools, equity and options orders
use a review-then-place workflow:

1. Resolve or receive the exact account number. Do not default silently when
   multiple accounts exist.
2. Confirm the account is marked `agentic_allowed=true`.
3. For equities, call `review_equity_order` with symbol, side, order type,
   quantity or dollar amount, prices, time in force, and market-hours settings.
4. For options, resolve the option instrument, then call `review_option_order`
   with the account, leg, quantity, order type, price fields, and session.
5. Present alerts, buying-power impact, fees, collateral, and quote details to
   the user.
6. Only after explicit user confirmation, call `place_equity_order` or
   `place_option_order` with the same reviewed parameters and a UUID `ref_id`
   idempotency key.

Orders and cancellations are real-money actions. Agents should not place or
cancel them without explicit confirmation of the account, instrument, side,
quantity or notional value, order type, price constraints, and time in force.
