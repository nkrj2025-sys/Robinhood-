# Robinhood Trading

Python helpers for the Robinhood Crypto Trading API.

## Setup

Use Python 3 and install the package dependencies:

```bash
python3 -m pip install -r robinhood-api-trading/requirements.txt
```

Set credentials as environment variables. Do not hardcode real keys in the
repository.

```bash
export ROBINHOOD_API_KEY="your-api-key"
export ROBINHOOD_BASE64_PRIVATE_KEY="your-base64-ed25519-seed"
```

## How an agent places an order

The v2 client is designed to make order placement explicit:

1. The agent builds the order payload in dry-run mode.
2. A live order is submitted only when both `--live` is present and
   `ROBINHOOD_PLACE_REAL_ORDER=true` is set.
3. If `--account-number` is not provided for a live order, the client fetches
   the first crypto account and masks it in logs.

Dry-run a small market buy payload without credentials:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --place-order \
  --symbol BTC-USD \
  --side buy \
  --asset-quantity 0.000001
```

Submit the same order live:

```bash
export ROBINHOOD_PLACE_REAL_ORDER=true

python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --place-order \
  --live \
  --symbol BTC-USD \
  --side buy \
  --asset-quantity 0.000001
```

You can also pass a specific account and raw order config:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --place-order \
  --account-number "your-account-number" \
  --symbol ETH-USD \
  --side sell \
  --order-config-json '{"asset_quantity":"0.001"}'
```

Running without `--place-order` fetches accounts, loads the BTC-USD trading pair,
and prints an estimated price. It does not place an order.
