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

### Credentials and env loading

The script auto-loads a local `.env` file (if present) before reading environment variables.
`.env` is ignored by git.

Required credentials:
- `ROBINHOOD_API_KEY`
- `ROBINHOOD_BASE64_PRIVATE_KEY`

Example `.env`:

```bash
ROBINHOOD_API_KEY=your_api_key_here
ROBINHOOD_BASE64_PRIVATE_KEY=your_base64_ed25519_seed_here
```

Optional strategy variables:
- `ROBINHOOD_SYMBOL` (default: `BTC-USD`)
- `ROBINHOOD_LOOKBACK_TICKS` (default: `8`)
- `ROBINHOOD_MOMENTUM_THRESHOLD_PCT` (default: `0.20`)
- `ROBINHOOD_TRADE_NOTIONAL_USD` (default: `25`)
- `ROBINHOOD_MAX_POSITION_ASSET` (default: `0.01`)
- `ROBINHOOD_MAX_ITERATIONS` (default: `50`)
- `ROBINHOOD_POLL_INTERVAL_SECONDS` (default: `20`)
- `ROBINHOOD_STOP_LOSS_PCT` (default: `1.00`)
- `ROBINHOOD_TAKE_PROFIT_PCT` (default: `1.50`)
- `ROBINHOOD_MAX_LOSS_USD` (default: `20`)
- `ROBINHOOD_MAX_TRADES_PER_RUN` (default: `6`)
- `ROBINHOOD_COOLDOWN_ITERATIONS` (default: `2`)
- `ROBINHOOD_MAX_SPREAD_PCT` (default: `0.40`)
- `ROBINHOOD_REQUIRE_ESTIMATED_PRICE_CHECK` (default: `true`)
- `ROBINHOOD_MAX_ESTIMATED_PRICE_DEVIATION_PCT` (default: `0.75`)
- `ROBINHOOD_WATCHLIST_SYMBOLS` (comma-separated allowed symbols; if set, `ROBINHOOD_SYMBOL` must be included)
- `ROBINHOOD_PLACE_REAL_ORDER` (default: `false`)
- `ROBINHOOD_CONNECTIVITY_CHECK_ONLY` (default: `false`)
- `ROBINHOOD_TRADE_AUDIT_LOG_PATH` (default: `logs/trade_audit.jsonl`)

`ROBINHOOD_PLACE_REAL_ORDER=true` enables live orders. Keep it `false` while tuning.

For a credentials/network smoke test without running strategy loop:

```bash
ROBINHOOD_CONNECTIVITY_CHECK_ONLY=true python3 robinhood-api-trading/robinhood_api_trading_v2.py
```

### Order decision audit log

Every cycle writes JSONL audit entries (trade executed, skipped, blocked by risk checks,
or halted by guardrails) to `logs/trade_audit.jsonl` by default.

### Pre-trade safety gates (before any order)

- spread filter must pass (`ROBINHOOD_MAX_SPREAD_PCT`)
- estimated price review must pass (`ROBINHOOD_REQUIRE_ESTIMATED_PRICE_CHECK=true`)
- estimated-vs-mid deviation must be within limit
  (`ROBINHOOD_MAX_ESTIMATED_PRICE_DEVIATION_PCT`)
- symbol must pass watchlist gate when configured
  (`ROBINHOOD_WATCHLIST_SYMBOLS`)

### Lower-loss starter profile

```bash
ROBINHOOD_TRADE_NOTIONAL_USD=5
ROBINHOOD_MAX_POSITION_ASSET=0.002
ROBINHOOD_STOP_LOSS_PCT=0.50
ROBINHOOD_TAKE_PROFIT_PCT=0.80
ROBINHOOD_MAX_LOSS_USD=5
ROBINHOOD_MAX_TRADES_PER_RUN=3
ROBINHOOD_COOLDOWN_ITERATIONS=4
ROBINHOOD_MAX_SPREAD_PCT=0.20
ROBINHOOD_REQUIRE_ESTIMATED_PRICE_CHECK=true
ROBINHOOD_MAX_ESTIMATED_PRICE_DEVIATION_PCT=0.50
ROBINHOOD_WATCHLIST_SYMBOLS=BTC-USD,ETH-USD
ROBINHOOD_PLACE_REAL_ORDER=false
```
