"""Core execution engine: fetches market data, asks strategy for signals, applies simple risk checks, submits orders."""
import time
import logging
from typing import Optional, Dict, Any
import pandas as pd

from trading_agent.utils.config import Config
from trading_agent.broker.adapters.alpaca import AlpacaAdapter
from trading_agent.core.strategy import Strategy, MACrossover
from trading_agent.utils.logger import setup_logging

logger = logging.getLogger(__name__)


class Engine:
    def __init__(self, config: Config, strategy: Strategy):
        setup_logging(config.log_level)
        self.config = config
        self.strategy = strategy
        self.broker = AlpacaAdapter(config.alpaca_api_key, config.alpaca_api_secret, config.alpaca_base_url, use_paper=config.paper)
        self.running = False

    def _fetch_bars_as_df(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> pd.DataFrame:
        raw = self.broker.get_latest_bar(symbol, timeframe=timeframe, limit=limit)
        if not raw:
            return pd.DataFrame()
        df = pd.DataFrame(raw)
        # normalize fields if necessary
        # ensure close exists
        for col in ['close', 'open', 'high', 'low', 'timestamp', 'volume']:
            if col not in df.columns:
                df[col] = None
        return df

    def _risk_check_and_size(self, symbol: str) -> float:
        # naive fixed-size for demo: buy quantity = floor((cash * pct) / price)
        account = self.broker.get_account()
        cash = float(account.get('cash', 0))
        max_pct = self.config.max_position_pct
        latest_price = None
        bars = self._fetch_bars_as_df(symbol, limit=1)
        if not bars.empty:
            latest_price = float(bars['close'].iloc[-1])
        if latest_price is None or latest_price <= 0:
            return 0.0
        alloc = cash * max_pct
        qty = max(1, int(alloc / latest_price))
        return qty

    def _process_signal(self, signal: Dict[str, Any]):
        action = signal.get('action')
        symbol = signal.get('symbol')
        logger.info("Processing signal: %s", signal)
        qty = self._risk_check_and_size(symbol)
        if qty <= 0:
            logger.warning("Calculated qty=0, skipping order")
            return
        if action == 'buy':
            order = self.broker.submit_order(symbol, qty, side='buy')
            logger.info("Order submitted: %s", order)
        elif action == 'sell':
            # for simplicity, issue a market sell of all positions in symbol
            positions = self.broker.get_positions()
            pos_qty = 0
            for p in positions:
                if p.get('symbol') == symbol:
                    pos_qty = int(float(p.get('qty', 0)))
            if pos_qty > 0:
                order = self.broker.submit_order(symbol, pos_qty, side='sell')
                logger.info("Sell order submitted: %s", order)
            else:
                logger.info("No position to sell for %s", symbol)

    def start(self, symbol: str):
        logger.info("Starting engine for %s (paper=%s)", symbol, self.config.paper)
        self.running = True
        while self.running:
            try:
                df = self._fetch_bars_as_df(symbol, timeframe=self.config.timeframe, limit=self.config.data_limit)
                if df.empty:
                    logger.debug("No bars returned, sleeping")
                else:
                    signal = self.strategy.on_bar(df)
                    if signal:
                        self._process_signal(signal)
                time.sleep(self.config.poll_interval)
            except KeyboardInterrupt:
                logger.info("Interrupted by user, stopping")
                self.running = False
            except Exception as e:
                logger.exception("Error in main loop: %s", e)
                time.sleep(5)

    def stop(self):
        self.running = False
