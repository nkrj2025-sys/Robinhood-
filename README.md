# Robinhood Trading

Crypto trading bot using Robinhood's crypto API with:
- Authenticated API client (Ed25519 signed requests)
- Momentum-based strategy loop
- Risk controls (buying power and max position caps)
- Dry-run mode by default (safe testing)

## Run

```bash
python3 robinhood-api-trading/robinhood_api_trading_v2.py
```

Required environment variables:
- `ROBINHOOD_API_KEY`
- `ROBINHOOD_BASE64_PRIVATE_KEY`

Optional strategy variables:
- `ROBINHOOD_SYMBOL` (default: `BTC-USD`)
- `ROBINHOOD_LOOKBACK_TICKS` (default: `8`)
- `ROBINHOOD_MOMENTUM_THRESHOLD_PCT` (default: `0.20`)
- `ROBINHOOD_TRADE_NOTIONAL_USD` (default: `25`)
- `ROBINHOOD_MAX_POSITION_ASSET` (default: `0.01`)
- `ROBINHOOD_MAX_ITERATIONS` (default: `50`)
- `ROBINHOOD_POLL_INTERVAL_SECONDS` (default: `20`)
- `ROBINHOOD_PLACE_REAL_ORDER` (default: `false`)

`ROBINHOOD_PLACE_REAL_ORDER=true` enables live orders. Keep it `false` while tuning.
