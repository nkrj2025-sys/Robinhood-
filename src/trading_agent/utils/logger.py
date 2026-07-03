"""Simple structured logger setup."""
import logging


def setup_logging(level: str = 'INFO'):
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
