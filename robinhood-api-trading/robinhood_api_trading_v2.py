import argparse
import base64
import datetime
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple
import urllib.parse
import uuid

import requests


DEFAULT_ORDER_SYMBOL = "BTC-USD"
DEFAULT_ASSET_QUANTITY = "0.000001"


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
        except ImportError as error:
            raise RuntimeError(
                "PyNaCl is required for signed Robinhood requests. Install "
                "dependencies with: python3 -m pip install -r "
                "robinhood-api-trading/requirements.txt"
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
        body = build_order_body(
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


def build_market_order_config(
    asset_quantity: Optional[str], quote_amount: Optional[str]
) -> Dict[str, str]:
    if bool(asset_quantity) == bool(quote_amount):
        raise ValueError("Specify exactly one of asset_quantity or quote_amount.")

    if asset_quantity:
        return {"asset_quantity": asset_quantity}
    if quote_amount is None:
        raise ValueError("Specify quote_amount.")
    return {"quote_amount": quote_amount}


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


def require_trading_pair(
    trading_pairs: Sequence[Dict[str, Any]], symbol: str
) -> Dict[str, Any]:
    for trading_pair in trading_pairs:
        if trading_pair.get("symbol") == symbol:
            return trading_pair

    raise RuntimeError(f"Trading pair {symbol} was not returned by Robinhood.")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or place a guarded Robinhood Crypto market order."
    )
    parser.add_argument(
        "--symbol",
        default=DEFAULT_ORDER_SYMBOL,
        help=f"Trading pair symbol to order. Default: {DEFAULT_ORDER_SYMBOL}",
    )
    parser.add_argument(
        "--side",
        choices=("buy", "sell"),
        default="buy",
        help="Order side. Default: buy",
    )
    quantity_group = parser.add_mutually_exclusive_group()
    quantity_group.add_argument(
        "--asset-quantity",
        help=f"Crypto asset quantity. Default: {DEFAULT_ASSET_QUANTITY}",
    )
    quantity_group.add_argument(
        "--quote-amount",
        help="USD quote amount for the market order instead of asset quantity.",
    )
    parser.add_argument(
        "--client-order-id",
        help="Client order UUID. Defaults to a newly generated UUID.",
    )
    parser.add_argument(
        "--account-number",
        help="Robinhood crypto account number. If omitted, the first account is used.",
    )
    parser.add_argument(
        "--check-market",
        action="store_true",
        help=(
            "Fetch account, trading-pair, and estimated-price data during a dry run. "
            "Live orders always perform account and trading-pair checks."
        ),
    )
    parser.add_argument(
        "--skip-estimate",
        action="store_true",
        help="Skip the estimated-price request before the live-order gate.",
    )
    parser.add_argument(
        "--place-real-order",
        action="store_true",
        help=(
            "Submit the order. For safety this must be combined with "
            "ROBINHOOD_PLACE_REAL_ORDER=true."
        ),
    )
    return parser.parse_args(argv)


def should_place_real_order(args: argparse.Namespace) -> bool:
    return (
        args.place_real_order
        and os.environ.get("ROBINHOOD_PLACE_REAL_ORDER", "").lower() == "true"
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    asset_quantity = args.asset_quantity
    if not asset_quantity and not args.quote_amount:
        asset_quantity = DEFAULT_ASSET_QUANTITY

    client_order_id = args.client_order_id or str(uuid.uuid4())
    order_config = build_market_order_config(
        asset_quantity=asset_quantity, quote_amount=args.quote_amount
    )
    order_body = build_order_body(
        client_order_id=client_order_id,
        side=args.side,
        order_type="market",
        symbol=args.symbol,
        order_config=order_config,
    )

    print("Prepared market order:")
    print(json.dumps(order_body, indent=2))

    live_order = should_place_real_order(args)
    partial_live_confirmation = (
        args.place_real_order
        or os.environ.get("ROBINHOOD_PLACE_REAL_ORDER", "").lower() == "true"
    )
    if not args.check_market and not live_order:
        if partial_live_confirmation:
            print(
                "Dry run mode: live submission requires both --place-real-order "
                "and ROBINHOOD_PLACE_REAL_ORDER=true."
            )
        else:
            print(
                "Dry run mode: add --check-market to fetch Robinhood market data, "
                "or add --place-real-order and set ROBINHOOD_PLACE_REAL_ORDER=true "
                "to place a live order."
            )
        return

    api_key = os.environ.get("ROBINHOOD_API_KEY", "")
    base64_private_key = os.environ.get("ROBINHOOD_BASE64_PRIVATE_KEY", "")

    if not api_key or not base64_private_key:
        print(
            "Dry run mode: set ROBINHOOD_API_KEY and "
            "ROBINHOOD_BASE64_PRIVATE_KEY to fetch account data or place orders."
        )
        return

    api_trading_client = CryptoAPITradingV2(
        api_key=api_key, base64_private_key=base64_private_key
    )

    account_number = args.account_number
    if not account_number:
        accounts = api_trading_client.get_accounts()
        if (
            not isinstance(accounts, dict)
            or "results" not in accounts
            or not accounts["results"]
        ):
            raise RuntimeError(f"Unable to fetch accounts: {accounts}")
        account_number = accounts["results"][0]["account_number"]
    print(f"Using account: ****{account_number[-4:]}")

    trading_pairs = api_trading_client.get_trading_pairs(args.symbol)
    trading_pair = require_trading_pair(trading_pairs, args.symbol)
    print(f"Validated trading pair: {trading_pair['symbol']}")

    if not args.skip_estimate and asset_quantity:
        estimated_price = api_trading_client.get_estimated_price(
            symbol=args.symbol, side="both", quantity=asset_quantity
        )
        print("Estimated price:")
        print(json.dumps(estimated_price, indent=2))
    elif not args.skip_estimate:
        print("Skipping estimated price because quote amount was provided.")

    if live_order:
        order_response = api_trading_client.place_order(
            account_number=account_number,
            client_order_id=client_order_id,
            side=args.side,
            order_type="market",
            symbol=args.symbol,
            order_config=order_config,
        )
        print("Order response:")
        print(json.dumps(order_response, indent=2))
    elif partial_live_confirmation:
        print(
            "Dry run mode: live submission requires both --place-real-order "
            "and ROBINHOOD_PLACE_REAL_ORDER=true."
        )
    else:
        print(
            "Dry run mode: add --place-real-order and set "
            "ROBINHOOD_PLACE_REAL_ORDER=true to place a live order."
        )


if __name__ == "__main__":
    main()
