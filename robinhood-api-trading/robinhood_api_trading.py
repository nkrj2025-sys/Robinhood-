import argparse
import base64
import binascii
import datetime
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
import urllib.parse
import uuid

import requests
from nacl.signing import SigningKey


DEFAULT_BASE_URL = "https://trading.robinhood.com"
LIVE_ORDER_ENV_VAR = "ROBINHOOD_PLACE_REAL_ORDER"


class RobinhoodAPIError(RuntimeError):
    def __init__(self, method: str, path: str, status_code: int, payload: Any):
        super().__init__(
            f"Robinhood API request failed: {method} {path} returned "
            f"HTTP {status_code}: {json.dumps(payload, default=str)}"
        )
        self.method = method
        self.path = path
        self.status_code = status_code
        self.payload = payload


class CryptoAPITrading:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base64_private_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        session: Optional[requests.Session] = None,
    ):
        self.api_key = (api_key or os.environ.get("ROBINHOOD_API_KEY", "")).strip()
        encoded_private_key = (
            base64_private_key
            if base64_private_key is not None
            else os.environ.get("ROBINHOOD_BASE64_PRIVATE_KEY", "")
        ).strip()

        if not self.api_key:
            raise ValueError("Missing ROBINHOOD_API_KEY")
        if not encoded_private_key:
            raise ValueError("Missing ROBINHOOD_BASE64_PRIVATE_KEY")

        try:
            private_key_seed = base64.b64decode(encoded_private_key, validate=True)
            self.private_key = SigningKey(private_key_seed)
        except (binascii.Error, ValueError) as error:
            raise ValueError(
                "ROBINHOOD_BASE64_PRIVATE_KEY must be a base64-encoded "
                "Ed25519 private key seed"
            ) from error

        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    @staticmethod
    def _get_current_timestamp() -> int:
        return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

    @staticmethod
    def get_query_params(params: Mapping[str, Any]) -> str:
        if not params:
            return ""

        query_pairs: List[Tuple[str, str]] = []
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                query_pairs.extend(
                    (key, str(item)) for item in value if item is not None
                )
            else:
                query_pairs.append((key, str(value)))

        if not query_pairs:
            return ""
        return "?" + urllib.parse.urlencode(query_pairs)

    def make_api_request(self, method: str, path: str, body: str = "") -> Any:
        method = method.upper()
        timestamp = self._get_current_timestamp()
        headers = self.get_authorization_header(method, path, body, timestamp)
        url = self.base_url + path

        try:
            response = self.session.request(
                method,
                url,
                headers=headers,
                data=body if body else None,
                timeout=10,
            )
        except requests.RequestException as e:
            raise RuntimeError(f"Error making API request: {e}") from e

        try:
            payload = response.json()
        except ValueError:
            payload = {"status_code": response.status_code, "text": response.text}

        if not response.ok:
            raise RobinhoodAPIError(method, path, response.status_code, payload)
        return payload

    def get_authorization_header(
        self, method: str, path: str, body: str, timestamp: int
    ) -> Dict[str, str]:
        message_to_sign = f"{self.api_key}{timestamp}{path}{method}{body}"
        signed = self.private_key.sign(message_to_sign.encode("utf-8"))

        return {
            "x-api-key": self.api_key,
            "x-signature": base64.b64encode(signed.signature).decode("utf-8"),
            "x-timestamp": str(timestamp),
            "Content-Type": "application/json",
        }

    def get_account(self) -> Any:
        path = "/api/v1/crypto/trading/accounts/"
        return self.make_api_request("GET", path)

    def get_accounts(self) -> Any:
        return self.get_account()

    # Symbols must be formatted as trading pairs, e.g. "BTC-USD".
    def get_trading_pairs(self, *symbols: Optional[str]) -> Any:
        query_params = self.get_query_params(
            {"symbol": [symbol for symbol in symbols if symbol]}
        )
        path = f"/api/v1/crypto/trading/trading_pairs/{query_params}"
        return self.make_api_request("GET", path)

    # Asset codes must be short crypto symbols, e.g. "BTC" or "ETH".
    def get_holdings(self, *asset_codes: Optional[str]) -> Any:
        query_params = self.get_query_params(
            {"asset_code": [asset_code for asset_code in asset_codes if asset_code]}
        )
        path = f"/api/v1/crypto/trading/holdings/{query_params}"
        return self.make_api_request("GET", path)

    # Symbols must be formatted as trading pairs, e.g. "BTC-USD".
    def get_best_bid_ask(self, *symbols: Optional[str]) -> Any:
        query_params = self.get_query_params(
            {"symbol": [symbol for symbol in symbols if symbol]}
        )
        path = f"/api/v1/crypto/marketdata/best_bid_ask/{query_params}"
        return self.make_api_request("GET", path)

    # The symbol argument must be formatted in a trading pair, e.g "BTC-USD", "ETH-USD"
    # The side argument must be "bid", "ask", or "both".
    # Multiple quantities can be specified in the quantity argument, e.g. "0.1,1,1.999".
    def get_estimated_price(self, symbol: str, side: str, quantity: str) -> Any:
        query_params = self.get_query_params(
            {"symbol": symbol, "side": side, "quantity": quantity}
        )
        path = f"/api/v1/crypto/marketdata/estimated_price/{query_params}"
        return self.make_api_request("GET", path)

    @staticmethod
    def build_order_body(
        client_order_id: str,
        side: str,
        order_type: str,
        symbol: str,
        order_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "client_order_id": client_order_id,
            "side": side,
            "type": order_type,
            "symbol": symbol,
            f"{order_type}_order_config": order_config,
        }

    def place_order(
        self,
        client_order_id: str,
        side: str,
        order_type: str,
        symbol: str,
        order_config: Dict[str, Any],
    ) -> Any:
        body = self.build_order_body(
            client_order_id=client_order_id,
            side=side,
            order_type=order_type,
            symbol=symbol,
            order_config=order_config,
        )
        path = "/api/v1/crypto/trading/orders/"
        body_json = json.dumps(body, separators=(",", ":"), sort_keys=True)
        return self.make_api_request("POST", path, body_json)

    def cancel_order(self, order_id: str) -> Any:
        path = f"/api/v1/crypto/trading/orders/{order_id}/cancel/"
        return self.make_api_request("POST", path)

    def get_order(self, order_id: str) -> Any:
        path = f"/api/v1/crypto/trading/orders/{order_id}/"
        return self.make_api_request("GET", path)

    def get_orders(self) -> Any:
        path = "/api/v1/crypto/trading/orders/"
        return self.make_api_request("GET", path)


def _json_default(value: Any) -> str:
    return str(value)


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, default=_json_default))


def mask_account_number(account_number: Any) -> Any:
    if not isinstance(account_number, str) or len(account_number) <= 4:
        return account_number
    return f"****{account_number[-4:]}"


def redact_account_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                mask_account_number(item)
                if key == "account_number"
                else redact_account_numbers(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_account_numbers(item) for item in value]
    return value


def build_order_config(args: argparse.Namespace) -> Dict[str, Any]:
    if args.order_config_json:
        try:
            order_config = json.loads(args.order_config_json)
        except ValueError as error:
            raise ValueError("--order-config-json must be valid JSON") from error
        if not isinstance(order_config, dict):
            raise ValueError("--order-config-json must decode to a JSON object")
        if not order_config or any(value == "" for value in order_config.values()):
            raise ValueError("--order-config-json must contain non-empty values")
        return order_config

    order_config: Dict[str, Any] = {}
    for key in (
        "asset_quantity",
        "quote_amount",
        "limit_price",
        "stop_price",
        "time_in_force",
    ):
        value = getattr(args, key)
        if value:
            order_config[key] = value

    if not order_config:
        raise ValueError(
            "Provide order sizing with --asset-quantity, --quote-amount, "
            "or --order-config-json"
        )
    return order_config


def load_client(args: argparse.Namespace) -> CryptoAPITrading:
    return CryptoAPITrading(base_url=args.base_url)


def handle_connect(args: argparse.Namespace) -> int:
    accounts = load_client(args).get_accounts()
    print("Connected to Robinhood Crypto Trading API.")
    print_json(redact_account_numbers(accounts))
    return 0


def handle_accounts(args: argparse.Namespace) -> int:
    print_json(redact_account_numbers(load_client(args).get_accounts()))
    return 0


def handle_holdings(args: argparse.Namespace) -> int:
    print_json(load_client(args).get_holdings(*args.asset_code))
    return 0


def handle_quote(args: argparse.Namespace) -> int:
    print_json(load_client(args).get_best_bid_ask(*args.symbol))
    return 0


def handle_estimate(args: argparse.Namespace) -> int:
    print_json(
        load_client(args).get_estimated_price(
            symbol=args.symbol,
            side=args.side,
            quantity=args.quantity,
        )
    )
    return 0


def handle_orders(args: argparse.Namespace) -> int:
    print_json(load_client(args).get_orders())
    return 0


def handle_cancel(args: argparse.Namespace) -> int:
    live_trading_enabled = os.environ.get(LIVE_ORDER_ENV_VAR, "").lower() == "true"
    if not args.confirm_live_trade or not live_trading_enabled:
        raise ValueError(
            f"Canceling an order is live account activity. Pass --confirm-live-trade "
            f"and set {LIVE_ORDER_ENV_VAR}=true to continue."
        )

    print_json(load_client(args).cancel_order(args.order_id))
    return 0


def handle_order(args: argparse.Namespace) -> int:
    order_config = build_order_config(args)
    client_order_id = args.client_order_id or str(uuid.uuid4())
    order_body = CryptoAPITrading.build_order_body(
        client_order_id=client_order_id,
        side=args.side,
        order_type=args.order_type,
        symbol=args.symbol,
        order_config=order_config,
    )

    live_trading_enabled = os.environ.get(LIVE_ORDER_ENV_VAR, "").lower() == "true"
    if not args.confirm_live_trade:
        print("Dry run: no order was submitted.")
        print_json(order_body)
        print(
            f"To submit this order, rerun with --confirm-live-trade and "
            f"{LIVE_ORDER_ENV_VAR}=true."
        )
        return 0

    if not live_trading_enabled:
        raise ValueError(
            f"Refusing to place a live order until {LIVE_ORDER_ENV_VAR}=true is set."
        )

    print_json(
        load_client(args).place_order(
            client_order_id=client_order_id,
            side=args.side,
            order_type=args.order_type,
            symbol=args.symbol,
            order_config=order_config,
        )
    )
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ROBINHOOD_BASE_URL", DEFAULT_BASE_URL),
        help="Robinhood Trading API base URL.",
    )


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Connect to the Robinhood Crypto Trading API and submit crypto "
            "orders when explicitly confirmed."
        )
    )
    add_common_arguments(parser)

    subparsers = parser.add_subparsers(dest="command", required=True)

    connect_parser = subparsers.add_parser(
        "connect", help="Validate credentials by fetching crypto trading accounts."
    )
    connect_parser.set_defaults(handler=handle_connect)

    accounts_parser = subparsers.add_parser(
        "accounts", help="Fetch crypto trading accounts."
    )
    accounts_parser.set_defaults(handler=handle_accounts)

    holdings_parser = subparsers.add_parser("holdings", help="Fetch crypto holdings.")
    holdings_parser.add_argument(
        "--asset-code",
        action="append",
        default=[],
        help="Optional asset code filter, for example BTC. Repeat for multiple assets.",
    )
    holdings_parser.set_defaults(handler=handle_holdings)

    quote_parser = subparsers.add_parser("quote", help="Fetch best bid/ask quotes.")
    quote_parser.add_argument(
        "symbol", nargs="+", help="Trading pair, for example BTC-USD."
    )
    quote_parser.set_defaults(handler=handle_quote)

    estimate_parser = subparsers.add_parser(
        "estimate", help="Fetch estimated price for a quantity."
    )
    estimate_parser.add_argument("symbol", help="Trading pair, for example BTC-USD.")
    estimate_parser.add_argument("--side", choices=("bid", "ask", "both"), required=True)
    estimate_parser.add_argument("--quantity", required=True)
    estimate_parser.set_defaults(handler=handle_estimate)

    orders_parser = subparsers.add_parser("orders", help="List orders.")
    orders_parser.set_defaults(handler=handle_orders)

    cancel_parser = subparsers.add_parser("cancel", help="Cancel an order.")
    cancel_parser.add_argument("order_id")
    cancel_parser.add_argument("--confirm-live-trade", action="store_true")
    cancel_parser.set_defaults(handler=handle_cancel)

    order_parser = subparsers.add_parser(
        "order",
        help="Build an order and optionally submit it when live trading is confirmed.",
    )
    order_parser.add_argument(
        "--symbol", required=True, help="Trading pair, for example BTC-USD."
    )
    order_parser.add_argument("--side", choices=("buy", "sell"), required=True)
    order_parser.add_argument(
        "--order-type",
        choices=("market", "limit", "stop_loss", "stop_limit"),
        default="market",
    )
    order_parser.add_argument("--asset-quantity", dest="asset_quantity")
    order_parser.add_argument("--quote-amount", dest="quote_amount")
    order_parser.add_argument("--limit-price", dest="limit_price")
    order_parser.add_argument("--stop-price", dest="stop_price")
    order_parser.add_argument("--time-in-force", dest="time_in_force")
    order_parser.add_argument(
        "--order-config-json",
        help="Raw order config JSON object. Overrides individual order config flags.",
    )
    order_parser.add_argument("--client-order-id")
    order_parser.add_argument("--confirm-live-trade", action="store_true")
    order_parser.set_defaults(handler=handle_order)

    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    try:
        return args.handler(args)
    except (RobinhoodAPIError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
