# Robinhood Trading

Python client examples for the Robinhood Crypto Trading API.

## How an agent places an order

An agent should only place a live order after it has:

1. Received explicit user instructions for the account, symbol, side, order type,
   and quantity or notional amount.
2. Shown the user a quote/estimated price and any relevant risks or alerts.
3. Received explicit confirmation to submit the live order.

The Postgres MCP install link configures database access only. It does not give an
agent permission or ability to place Robinhood orders.

## Crypto order flow in this repo

Use `robinhood-api-trading/robinhood_api_trading_v2.py` for the guarded crypto
flow:

```bash
export ROBINHOOD_API_KEY="..."
export ROBINHOOD_BASE64_PRIVATE_KEY="..."

# Dry run: loads account data and prints an estimated BTC-USD price.
python3 robinhood-api-trading/robinhood_api_trading_v2.py

# Live order: only after user confirmation.
ROBINHOOD_PLACE_REAL_ORDER=true \
python3 robinhood-api-trading/robinhood_api_trading_v2.py
```

In code, the live order call is:

```python
order_response = api_trading_client.place_order(
    account_number=account_number,
    client_order_id=str(uuid.uuid4()),
    side="buy",
    order_type="market",
    symbol="BTC-USD",
    order_config={"asset_quantity": "0.000001"},
)
```

The request is signed with the Ed25519 private key from
`ROBINHOOD_BASE64_PRIVATE_KEY` and sent to
`https://trading.robinhood.com/api/v2/crypto/trading/orders/`.

Do not commit real API keys or private keys. Set them with environment variables
or Cursor secrets.

## Robinhood MCP brokerage order flow

If an agent is using the Robinhood MCP server for equities or options, it should:

1. Use `get_accounts` only to identify available accounts; do not silently choose
   an account when the user has not specified one.
2. Call `review_equity_order` or `review_option_order` first.
3. Present the review result, estimated cost, quote, and alerts to the user.
4. Call `place_equity_order` or `place_option_order` only after explicit
   confirmation.
5. Reuse the same UUID `ref_id` for retries of the same logical order to preserve
   idempotency.
