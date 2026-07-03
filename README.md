# Robinhood Trading

Python client examples for the Robinhood Crypto Trading API.

## How the agent places a crypto order

The order-placement flow lives in
`robinhood-api-trading/robinhood_api_trading_v2.py`.

By default, the script **does not place a live order**. It:

1. Reads `ROBINHOOD_API_KEY` and `ROBINHOOD_BASE64_PRIVATE_KEY` from the
   environment.
2. Signs each request with the Ed25519 private key.
3. Fetches the crypto trading account.
4. Loads the `BTC-USD` trading pair.
5. Requests an estimated price for a tiny BTC quantity.
6. Stops in dry-run mode unless live ordering is explicitly enabled.

To verify the full setup without placing an order:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py
```

To allow the script to submit its example order, set the live-order guard:

```bash
ROBINHOOD_PLACE_REAL_ORDER=true \
python3 robinhood-api-trading/robinhood_api_trading_v2.py
```

When live ordering is enabled, the script submits a POST request to:

```text
/api/v2/crypto/trading/orders/?account_number=<account_number>
```

with a body shaped like:

```json
{
  "client_order_id": "<uuid>",
  "side": "buy",
  "type": "market",
  "symbol": "BTC-USD",
  "market_order_config": {
    "asset_quantity": "0.000001"
  }
}
```

Do not hardcode Robinhood credentials in this repository. Configure
`ROBINHOOD_API_KEY` and `ROBINHOOD_BASE64_PRIVATE_KEY` as environment variables
or Cursor secrets before running the client.
