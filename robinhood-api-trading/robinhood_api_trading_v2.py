import argparse
import base64
import datetime
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import urllib.parse
import uuid

import requests


LIVE_ORDER_CONFIRMATION = "PLACE LIVE ORDER"


class CryptoAPITradingV2:
    def __init__(self, api_key: str, base64_private_key: str):
        if not api_key:
            raise ValueError("Missing ROBINHOOD_API_KEY")
        if not base64_private_key:
            raise ValueError("Missing ROBINHOOD_BASE64_PRIVATE_KEY")

        self.api_key = api_key
        private_key_seed = base64.b64decode(base64_private_key)
        try:
            from nacl.signing import SigningKey
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "Missing dependency 'pynacl'. Install dependencies with "
                "python3 -m pip install -r robinhood-api-trading/requirements.txt."
            ) from error

        self.private_key = SigningKey(private_key_seed)
        self.base_url = "https://trading.robinhood.com"
        self.session = requests.Session()

    @staticmethod
    def _get_current_timestamp() -> int:
        return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

    @staticmethod
    def get_query_params(params_dict: Dict[str, Any]) -> str:
        """
        Build query parameter string from a dictionary.
        - Single values: {"key1": "value1", "key2": "value2"}
        - Multiple values for same key: {"symbol": ["BTC-USD", "ETH-USD"]}
        """
        if not params_dict:
            return ""

        query_pairs: List[Tuple[str, str]] = []
        for key, value in params_dict.items():
            if value is None:
                continue
            if isinstance(value, list):
                for list_value in value:
                    query_pairs.append((key, str(list_value)))
            else:
                query_pairs.append((key, str(value)))

        if not query_pairs:
            return ""
        return f"?{urllib.parse.urlencode(query_pairs)}"

    def make_api_request(self, method: str, path: str, body: str = "") -> Any:
        timestamp = self._get_current_timestamp()
        headers = self.get_authorization_header(method, path, body, timestamp)
        url = self.base_url + path

        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, timeout=10)
            elif method == "POST":
                response = self.session.post(url, headers=headers, data=body, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            try:
                return response.json()
            except ValueError:
                return {"status_code": response.status_code, "error": response.text}
        except requests.RequestException as error:
            return {"error": f"Error making API request: {error}"}

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

    def get_accounts(self) -> Any:
        path = "/api/v2/crypto/trading/accounts/"
        return self.make_api_request("GET", path)

    def get_trading_pairs(self, *symbols: Optional[str]) -> List[Dict[str, Any]]:
        params = {"symbol": [symbol for symbol in symbols if symbol]} if symbols else {}
        query_params = self.get_query_params(params)
        path = f"/api/v2/crypto/trading/trading_pairs/{query_params}"

        all_results: List[Dict[str, Any]] = []
        response = self.make_api_request("GET", path)
        if isinstance(response, dict) and response.get("error"):
            raise RuntimeError(response["error"])

        while isinstance(response, dict):
            results = response.get("results", [])
            if isinstance(results, list):
                all_results.extend(results)

            next_url = response.get("next")
            if not next_url:
                break

            next_path = next_url.replace(self.base_url, "")
            response = self.make_api_request("GET", next_path)

        return all_results

    def get_holdings(self, account_number: str, *asset_codes: Optional[str]) -> Any:
        params: Dict[str, Any] = {"account_number": account_number}
        if asset_codes:
            params["asset_code"] = [asset for asset in asset_codes if asset]
        query_params = self.get_query_params(params)
        path = f"/api/v2/crypto/trading/holdings/{query_params}"
        return self.make_api_request("GET", path)

    def get_best_bid_ask(self, *symbols: str) -> Any:
        params = {"symbol": [symbol for symbol in symbols if symbol]} if symbols else {}
        query_params = self.get_query_params(params)
        path = f"/api/v2/crypto/marketdata/best_bid_ask/{query_params}"
        return self.make_api_request("GET", path)

    def get_estimated_price(self, symbol: str, side: str, quantity: str) -> Any:
        params = {"symbol": symbol, "side": side, "quantity": quantity}
        query_params = self.get_query_params(params)
        path = f"/api/v2/crypto/trading/estimated_price/{query_params}"
        return self.make_api_request("GET", path)

    def place_order(
        self,
        account_number: str,
        client_order_id: str,
        side: str,
        order_type: str,
        symbol: str,
        order_config: Dict[str, str],
    ) -> Any:
        body = self.build_order_body(
            client_order_id=client_order_id,
            side=side,
            order_type=order_type,
            symbol=symbol,
            order_config=order_config,
        )
        body_json = json.dumps(body, separators=(",", ":"), sort_keys=True)
        params = {"account_number": account_number}
        query_params = self.get_query_params(params)
        path = f"/api/v2/crypto/trading/orders/{query_params}"
        return self.make_api_request("POST", path, body_json)

    @staticmethod
    def build_order_body(
        client_order_id: str,
        side: str,
        order_type: str,
        symbol: str,
        order_config: Dict[str, str],
    ) -> Dict[str, Any]:
        return {
            "client_order_id": client_order_id,
            "side": side,
            "type": order_type,
            "symbol": symbol,
            f"{order_type}_order_config": order_config,
        }

    def cancel_order(self, order_id: str) -> Any:
        path = f"/api/v2/crypto/trading/orders/{order_id}/cancel/"
        return self.make_api_request("POST", path)

    def get_order(self, account_number: str, order_id: str) -> Any:
        params = {"account_number": account_number}
        query_params = self.get_query_params(params)
        path = f"/api/v2/crypto/trading/orders/{order_id}/{query_params}"
        return self.make_api_request("GET", path)

    def get_orders(self, account_number: str) -> Any:
        params = {"account_number": account_number}
        query_params = self.get_query_params(params)
        path = f"/api/v2/crypto/trading/orders/{query_params}"
        return self.make_api_request("GET", path)


def build_order_config(
    order_type: str,
    asset_quantity: Optional[str],
    quote_amount: Optional[str],
    limit_price: Optional[str],
    time_in_force: Optional[str],
) -> Dict[str, str]:
    if not asset_quantity and not quote_amount:
        raise ValueError("Pass --asset-quantity or --quote-amount for the order size.")
    if asset_quantity and quote_amount:
        raise ValueError("Pass only one of --asset-quantity or --quote-amount.")

    order_config: Dict[str, str] = {}
    if asset_quantity:
        order_config["asset_quantity"] = asset_quantity
    if quote_amount:
        order_config["quote_amount"] = quote_amount

    if order_type == "limit":
        if not limit_price:
            raise ValueError("Limit orders require --limit-price.")
        order_config["limit_price"] = limit_price
        if time_in_force:
            order_config["time_in_force"] = time_in_force
    elif limit_price:
        raise ValueError("--limit-price is only valid with --order-type limit.")
    elif time_in_force:
        raise ValueError("--time-in-force is only valid with --order-type limit.")

    return order_config


def validate_live_order_gates(
    place: bool,
    account_number: Optional[str],
    confirmation: Optional[str],
    environ: Mapping[str, str],
) -> None:
    if not place:
        return
    if not account_number:
        raise ValueError(
            "Live orders require --account-number or ROBINHOOD_CRYPTO_ACCOUNT_NUMBER."
        )
    if environ.get("ROBINHOOD_PLACE_REAL_ORDER", "").lower() != "true":
        raise ValueError("Set ROBINHOOD_PLACE_REAL_ORDER=true before placing a live order.")
    if confirmation != LIVE_ORDER_CONFIRMATION:
        raise ValueError(
            f'Pass --confirm-live-order "{LIVE_ORDER_CONFIRMATION}" to place a live order.'
        )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Robinhood crypto order preview by default. Live placement "
            "requires an account number, ROBINHOOD_PLACE_REAL_ORDER=true, --place, "
            "and an exact confirmation phrase."
        )
    )
    parser.add_argument(
        "--account-number",
        default=os.environ.get("ROBINHOOD_CRYPTO_ACCOUNT_NUMBER"),
        help="Crypto account number. Required for live orders.",
    )
    parser.add_argument("--symbol", default="BTC-USD", help="Trading pair, e.g. BTC-USD.")
    parser.add_argument("--side", choices=("buy", "sell"), default="buy")
    parser.add_argument("--order-type", choices=("market", "limit"), default="market")
    parser.add_argument("--asset-quantity", help="Asset quantity to trade.")
    parser.add_argument(
        "--quote-amount",
        help="USD notional amount to trade. Mutually exclusive with --asset-quantity.",
    )
    parser.add_argument("--limit-price", help="Limit price for limit orders.")
    parser.add_argument(
        "--time-in-force",
        choices=("gtc", "ioc", "fok"),
        help="Time in force for limit orders.",
    )
    parser.add_argument(
        "--client-order-id",
        help="Optional idempotency key. Defaults to a new UUID.",
    )
    parser.add_argument(
        "--preview-marketdata",
        action="store_true",
        help="Fetch trading-pair and quote data for the preview using API credentials.",
    )
    parser.add_argument(
        "--place",
        action="store_true",
        help="Submit a live order after all safety gates pass.",
    )
    parser.add_argument(
        "--confirm-live-order",
        help=f'Exact phrase required for live orders: "{LIVE_ORDER_CONFIRMATION}".',
    )
    args = parser.parse_args(argv)
    if not args.place and not args.asset_quantity and not args.quote_amount:
        args.asset_quantity = "0.000001"
    return args


def load_client_from_env() -> CryptoAPITradingV2:
    api_key = os.environ.get("ROBINHOOD_API_KEY", "")
    base64_private_key = os.environ.get("ROBINHOOD_BASE64_PRIVATE_KEY", "")

    if not api_key or not base64_private_key:
        raise ValueError(
            "Set ROBINHOOD_API_KEY and ROBINHOOD_BASE64_PRIVATE_KEY before running "
            "network calls."
        )

    return CryptoAPITradingV2(api_key=api_key, base64_private_key=base64_private_key)


def print_json(label: str, value: Any) -> None:
    print(label)
    print(json.dumps(value, indent=2))


def print_marketdata_preview(
    api_trading_client: CryptoAPITradingV2,
    symbol: str,
    side: str,
    asset_quantity: Optional[str],
) -> None:
    trading_pairs = api_trading_client.get_trading_pairs(symbol)
    print(f"Loaded trading pairs: {len(trading_pairs)}")

    if asset_quantity:
        estimated_price = api_trading_client.get_estimated_price(
            symbol=symbol,
            side="ask" if side == "buy" else "bid",
            quantity=asset_quantity,
        )
        print_json("Estimated price:", estimated_price)
        return

    best_bid_ask = api_trading_client.get_best_bid_ask(symbol)
    print_json("Best bid/ask:", best_bid_ask)


def extract_order_id(order_response: Any) -> Optional[str]:
    if not isinstance(order_response, dict):
        return None
    for key in ("id", "order_id"):
        value = order_response.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    client_order_id = args.client_order_id or str(uuid.uuid4())

    order_config = build_order_config(
        order_type=args.order_type,
        asset_quantity=args.asset_quantity,
        quote_amount=args.quote_amount,
        limit_price=args.limit_price,
        time_in_force=args.time_in_force,
    )
    order_preview = CryptoAPITradingV2.build_order_body(
        client_order_id=client_order_id,
        side=args.side,
        order_type=args.order_type,
        symbol=args.symbol,
        order_config=order_config,
    )
    print_json("Order preview:", order_preview)

    validate_live_order_gates(
        place=args.place,
        account_number=args.account_number,
        confirmation=args.confirm_live_order,
        environ=os.environ,
    )

    if args.preview_marketdata or args.place:
        api_trading_client = load_client_from_env()
        print_marketdata_preview(
            api_trading_client=api_trading_client,
            symbol=args.symbol,
            side=args.side,
            asset_quantity=args.asset_quantity,
        )
    else:
        api_trading_client = None

    if not args.place:
        print(
            "Dry run mode: add --place, set ROBINHOOD_PLACE_REAL_ORDER=true, "
            f'and pass --confirm-live-order "{LIVE_ORDER_CONFIRMATION}" to submit.'
        )
        return

    if api_trading_client is None:
        api_trading_client = load_client_from_env()

    order_response = api_trading_client.place_order(
        account_number=args.account_number,
        client_order_id=client_order_id,
        side=args.side,
        order_type=args.order_type,
        symbol=args.symbol,
        order_config=order_config,
    )
    print_json("Order response:", order_response)

    order_id = extract_order_id(order_response)
    if order_id:
        order_status = api_trading_client.get_order(args.account_number, order_id)
        print_json("Fetched order status:", order_status)


def cli(argv: Optional[Sequence[str]] = None) -> int:
    try:
        main(argv)
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
