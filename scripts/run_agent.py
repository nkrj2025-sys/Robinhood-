"""Entrypoint to run the agent."""
import argparse
from trading_agent.utils.config import Config
from trading_agent.core.strategy import MACrossover
from trading_agent.core.engine import Engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='AAPL')
    parser.add_argument('--paper', action='store_true')
    parser.add_argument('--short', type=int, default=10)
    parser.add_argument('--long', type=int, default=30)
    args = parser.parse_args()

    config = Config.from_env()
    config.paper = args.paper or config.paper

    strategy = MACrossover(short_window=args.short, long_window=args.long, symbol=args.symbol)
    engine = Engine(config, strategy)
    engine.start(args.symbol)


if __name__ == '__main__':
    main()
