# Safety and ToS notes for running a trading agent

This document summarizes safety considerations and Terms of Service (ToS) guidance.

Key points:
- Do NOT use undocumented Robinhood endpoints or reverse-engineered APIs. Doing so can violate their ToS and may lead to account suspension or legal issues.
- Use brokers that provide official APIs for automated trading (Alpaca, Interactive Brokers, Tradier, etc.). The scaffold uses Alpaca for this reason and because it supports paper trading.
- Always develop and test in paper/simulated mode before any live deployment.
- Implement monitoring, circuit breakers (max daily drawdown), and manual kill switches before trading live.

Recommended testing flow:
1. Unit tests for strategy and risk logic.
2. Backtesting on historical data.
3. Paper trading with the broker's paper environment.
4. Small-scale live test with strict risk limits.

