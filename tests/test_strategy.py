"""Basic unit tests for the MACrossover strategy."""
import pandas as pd
from trading_agent.core.strategy import MACrossover


def test_macrossover_no_signal_on_short_data():
    # fewer than long window -> no signal
    data = {
        'timestamp': pd.date_range(end=pd.Timestamp.now(), periods=10, freq='T'),
        'close': [100 + i for i in range(10)]
    }
    df = pd.DataFrame(data)
    strat = MACrossover(short_window=5, long_window=30)
    assert strat.on_bar(df) is None


def test_macrossover_generates_signal():
    # construct data where short MA > long MA
    prices = list(range(50, 80))
    df = pd.DataFrame({'timestamp': pd.date_range(end=pd.Timestamp.now(), periods=len(prices), freq='T'), 'close': prices})
    strat = MACrossover(short_window=3, long_window=10, symbol='TEST')
    sig = strat.on_bar(df)
    assert sig is not None
    assert sig.get('symbol') == 'TEST'
    assert sig.get('action') in ('buy', 'sell')
