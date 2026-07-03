"""Strategy interface and Moving Average Crossover implementation."""
from typing import Dict, Any, Optional
import pandas as pd


class Strategy:
    """Base strategy interface. Implement on_bar to return an order dict or None."""

    def on_bar(self, bars: pd.DataFrame) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class MACrossover(Strategy):
    def __init__(self, short_window: int = 10, long_window: int = 30, symbol: str = 'AAPL'):
        self.short_window = short_window
        self.long_window = long_window
        self.symbol = symbol
        self._last_signal = None

    def on_bar(self, bars: pd.DataFrame) -> Optional[Dict[str, Any]]:
        # bars: DataFrame with columns ['timestamp','open','high','low','close','volume']
        if len(bars) < self.long_window:
            return None
        df = bars.copy()
        df['close'] = pd.to_numeric(df['close'])
        short_ma = df['close'].rolling(self.short_window).mean().iloc[-1]
        long_ma = df['close'].rolling(self.long_window).mean().iloc[-1]

        signal = 'hold'
        if short_ma > long_ma:
            signal = 'long'
        elif short_ma < long_ma:
            signal = 'short'

        # simple signal edge: act only on change
        if signal == self._last_signal or signal == 'hold':
            return None

        self._last_signal = signal

        if signal == 'long':
            return {"action": "buy", "symbol": self.symbol}
        elif signal == 'short':
            return {"action": "sell", "symbol": self.symbol}
        return None
