# Robinhood Crypto Trading

Python client and command-line helper for the Robinhood Crypto Trading API.

## Setup

Install dependencies:

```bash
python3 -m pip install -r robinhood-api-trading/requirements.txt
```

Create API credentials in Robinhood, then provide them through environment
variables. Do not hardcode real keys in this repository.

```bash
export ROBINHOOD_API_KEY="your-api-key"
export ROBINHOOD_BASE64_PRIVATE_KEY="your-base64-ed25519-private-key-seed"
```

## Connect to the account

Validate the credentials and fetch the crypto trading accounts:

```bash
python3 robinhood-api-trading/robinhood_api_trading.py connect
```

The command masks account numbers in its output.

## Market data

```bash
python3 robinhood-api-trading/robinhood_api_trading.py quote BTC-USD
python3 robinhood-api-trading/robinhood_api_trading.py estimate BTC-USD --side both --quantity 0.0001
python3 robinhood-api-trading/robinhood_api_trading.py holdings --asset-code BTC
```

## Orders

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
