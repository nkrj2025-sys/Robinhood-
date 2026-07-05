import argparse
import base64
import datetime
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import uuid

import requests


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

    @staticmethod
    def build_order_payload(
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

    def place_order(
        self,
        account_number: str,
        client_order_id: str,
        side: str,
        order_type: str,
        symbol: str,
        order_config: Dict[str, str],
    ) -> Any:
        body = self.build_order_payload(
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


def _load_client_from_env() -> CryptoAPITradingV2:
    api_key = os.environ.get("ROBINHOOD_API_KEY", "")
    base64_private_key = os.environ.get("ROBINHOOD_BASE64_PRIVATE_KEY", "")

    if not api_key or not base64_private_key:
        raise ValueError(
            "Set ROBINHOOD_API_KEY and ROBINHOOD_BASE64_PRIVATE_KEY before running "
            "network calls."
        )

    return CryptoAPITradingV2(api_key=api_key, base64_private_key=base64_private_key)


def _parse_order_config(order_config_json: str, asset_quantity: str, quote_amount: str) -> Dict[str, str]:
    if order_config_json:
        parsed = json.loads(order_config_json)
        if not isinstance(parsed, dict):
            raise ValueError("--order-config-json must decode to a JSON object.")
        return {str(key): str(value) for key, value in parsed.items()}

    if asset_quantity and quote_amount:
        raise ValueError("Use either --asset-quantity or --quote-amount, not both.")
    if quote_amount:
        return {"quote_amount": quote_amount}
    return {"asset_quantity": asset_quantity}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Robinhood Crypto Trading API helper with dry-run order placement."
    )
    parser.add_argument(
        "--place-order",
        action="store_true",
        help="Build an order payload. Add --live and ROBINHOOD_PLACE_REAL_ORDER=true to submit it.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Submit the order to Robinhood. Requires ROBINHOOD_PLACE_REAL_ORDER=true.",
    )
    parser.add_argument(
        "--account-number",
        default="",
        help="Crypto account number. If omitted for live orders, the first account is used.",
    )
    parser.add_argument("--symbol", default="BTC-USD", help="Trading pair, for example BTC-USD.")
    parser.add_argument("--side", choices=["buy", "sell"], default="buy")
    parser.add_argument("--order-type", default="market", help="Order type, for example market.")
    parser.add_argument(
        "--asset-quantity",
        default="0.000001",
        help="Crypto quantity to trade when --order-config-json is not supplied.",
    )
    parser.add_argument(
        "--quote-amount",
        default="",
        help="Quote currency amount to trade when --order-config-json is not supplied.",
    )
    parser.add_argument(
        "--order-config-json",
        default="",
        help='Raw order config JSON, for example \'{"asset_quantity":"0.000001"}\'.',
    )
    parser.add_argument(
        "--client-order-id",
        default="",
        help="Optional idempotency key. A UUID is generated when omitted.",
    )
    return parser


def _print_json(label: str, value: Any) -> None:
    print(label)
    print(json.dumps(value, indent=2))


def _resolve_account_number(client: CryptoAPITradingV2, account_number: str) -> str:
    if account_number:
        return account_number

    accounts = client.get_accounts()
    if not isinstance(accounts, dict) or "results" not in accounts or not accounts["results"]:
        raise RuntimeError(f"Unable to fetch accounts: {accounts}")
    return accounts["results"][0]["account_number"]


def main() -> None:
    args = _build_parser().parse_args()

    if args.place_order:
        order_config = _parse_order_config(
            order_config_json=args.order_config_json,
            asset_quantity=args.asset_quantity,
            quote_amount=args.quote_amount,
        )
        client_order_id = args.client_order_id or str(uuid.uuid4())
        order_payload = CryptoAPITradingV2.build_order_payload(
            client_order_id=client_order_id,
            side=args.side,
            order_type=args.order_type,
            symbol=args.symbol,
            order_config=order_config,
        )

        if not args.live:
            _print_json("Dry run order payload:", order_payload)
            print("No order submitted. Add --live and set ROBINHOOD_PLACE_REAL_ORDER=true to submit.")
            return

        if os.environ.get("ROBINHOOD_PLACE_REAL_ORDER", "").lower() != "true":
            raise ValueError(
                "Live orders require both --live and ROBINHOOD_PLACE_REAL_ORDER=true."
            )

        api_trading_client = _load_client_from_env()
        account_number = _resolve_account_number(api_trading_client, args.account_number)
        print(f"Using account: ****{account_number[-4:]}")
        order_response = api_trading_client.place_order(
            account_number=account_number,
            client_order_id=client_order_id,
            side=args.side,
            order_type=args.order_type,
            symbol=args.symbol,
            order_config=order_config,
        )
        _print_json("Order response:", order_response)
        return

    api_trading_client = _load_client_from_env()

    accounts = api_trading_client.get_accounts()
    if not isinstance(accounts, dict) or "results" not in accounts or not accounts["results"]:
        raise RuntimeError(f"Unable to fetch accounts: {accounts}")

    account_number = accounts["results"][0]["account_number"]
    print(f"Using account: ****{account_number[-4:]}")

    trading_pairs = api_trading_client.get_trading_pairs("BTC-USD")
    print(f"Loaded trading pairs: {len(trading_pairs)}")

    estimated_price = api_trading_client.get_estimated_price(
        symbol="BTC-USD", side="both", quantity="0.000001"
    )
    print("Estimated price:")
    print(json.dumps(estimated_price, indent=2))

    print("Add --place-order to build a dry-run order payload.")


if __name__ == "__main__":
    main()
