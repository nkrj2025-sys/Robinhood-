# Robinhood Trading

Python examples for the Robinhood Crypto Trading API.

## Setup

Install dependencies:

```bash
python3 -m pip install -r robinhood-api-trading/requirements.txt
```

Set credentials as environment variables. Do not commit real keys:

```bash
export ROBINHOOD_API_KEY="..."
export ROBINHOOD_BASE64_PRIVATE_KEY="..."
```

## How the agent places an order

The v2 script builds the exact Robinhood order payload first and runs in dry-run
mode by default. A dry run does not submit an order and does not require
credentials:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --asset-quantity 0.000001
```

To submit a real crypto order, provide credentials and explicitly enable live
placement:

```bash
ROBINHOOD_PLACE_REAL_ORDER=true \
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --asset-quantity 0.000001
```

You can also pass `--place-real-order` instead of setting
`ROBINHOOD_PLACE_REAL_ORDER=true`. If `--account-number` is omitted for a live
order, the script fetches accounts and uses the first account returned by the
API.

Limit order example:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol ETH-USD \
  --side sell \
  --order-type limit \
  --asset-quantity 0.01 \
  --limit-price 5000
```

For advanced order config fields, pass the API config object directly:

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py \
  --symbol BTC-USD \
  --side buy \
  --order-type market \
  --order-config-json '{"asset_quantity":"0.000001"}'
```

Use `--dry-run` to force preview mode, even if
`ROBINHOOD_PLACE_REAL_ORDER=true` is present in the environment.
