"""Configuration loader."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    alpaca_api_key: str
    alpaca_api_secret: str
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    paper: bool = True
    timeframe: str = '1Min'
    data_limit: int = 200
    poll_interval: int = 60
    max_position_pct: float = 0.02
    max_daily_loss_pct: float = 0.01
    log_level: str = 'INFO'

    @classmethod
    def from_env(cls):
        return cls(
            alpaca_api_key=os.getenv('ALPACA_API_KEY', ''),
            alpaca_api_secret=os.getenv('ALPACA_API_SECRET', ''),
            alpaca_base_url=os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets'),
            paper=(os.getenv('PAPER', 'true').lower() == 'true'),
            timeframe=os.getenv('TIMEFRAME', '1Min'),
            data_limit=int(os.getenv('DATA_LIMIT', '200')),
            poll_interval=int(os.getenv('POLL_INTERVAL', '60')),
            max_position_pct=float(os.getenv('MAX_POSITION_PCT', '0.02')),
            max_daily_loss_pct=float(os.getenv('MAX_DAILY_LOSS_PCT', '0.01')),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
        )
