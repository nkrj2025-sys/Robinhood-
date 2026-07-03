"""Alpaca adapter using alpaca-trade-api
Wraps basic account, market data, and order operations.
Paper mode by default.
"""
from typing import Optional, Dict, Any, List
import logging

try:
    import alpaca_trade_api as tradeapi
except Exception:
    tradeapi = None

logger = logging.getLogger(__name__)


class AlpacaAdapter:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://paper-api.alpaca.markets", use_paper: bool = True):
        if tradeapi is None:
            raise RuntimeError("alpaca-trade-api is not installed. See requirements.txt")
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.use_paper = use_paper
        self._client = tradeapi.REST(api_key, api_secret, base_url, api_version='v2')
        logger.info("AlpacaAdapter initialized (paper=%s)", use_paper)

    def get_account(self) -> Dict[str, Any]:
        return self._client.get_account()._raw

    def get_positions(self) -> List[Dict[str, Any]]:
        return [p._raw for p in self._client.list_positions()]

    def get_latest_bar(self, symbol: str, timeframe: str = '1Min', limit: int = 100):
        # Returns list of bars as dicts
        barset = self._client.get_bars(symbol, timeframe, limit=limit).df
        # barset may include multi-index if multiple symbols; handle single symbol
        if isinstance(barset.columns, list):
            # if DataFrame with MultiIndex columns, extract symbol
            try:
                df = barset[symbol]
            except Exception:
                df = barset
        else:
            df = barset
        return df.reset_index().to_dict('records')

    def submit_order(self, symbol: str, qty: float, side: str = 'buy', order_type: str = 'market', time_in_force: str = 'gtc', limit_price: Optional[float] = None, stop_price: Optional[float] = None) -> Dict[str, Any]:
        params = {
            'symbol': symbol,
            'qty': qty,
            'side': side,
            'type': order_type,
            'time_in_force': time_in_force,
        }
        if limit_price is not None:
            params['limit_price'] = limit_price
        if stop_price is not None:
            params['stop_price'] = stop_price
        logger.info("Submitting order: %s", params)
        order = self._client.submit_order(**params)
        return order._raw

    def cancel_all_orders(self):
        self._client.cancel_all_orders()

    def close_position(self, symbol: str) -> Dict[str, Any]:
        order = self._client.close_position(symbol)
        return order._raw
