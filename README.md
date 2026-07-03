# Trading agent scaffold

This repository branch contains a scaffolded trading agent using Alpaca (paper trading by default).

Important safety notes
- This project is for educational and development purposes. Do not run live trading without understanding legal/ToS implications.
- Default mode is paper trading; confirm before switching to live keys.

Quick start
1. Create a Python 3.11 virtualenv and install deps:

   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

2. Copy .env.sample to .env and fill ALPACA_API_KEY and ALPACA_API_SECRET.

3. Run in paper mode:

   python scripts/run_agent.py --symbol AAPL --paper

Files added
- src/trading_agent/broker/adapters/alpaca.py
- src/trading_agent/core/engine.py
- src/trading_agent/core/strategy.py
- src/trading_agent/utils/config.py
- src/trading_agent/utils/logger.py
- scripts/run_agent.py
- requirements.txt, Dockerfile, .gitignore
- tests/ (basic unit tests)
- docs/notes_on_safety.md

Next steps
- Add CI, e2e tests with a simulated market, and optional integration with a secret manager.
