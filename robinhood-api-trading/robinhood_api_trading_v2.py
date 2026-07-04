import base64
import datetime
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import uuid

import requests
from nacl.signing import SigningKey


DEFAULT_ORDER_SYMBOL = "BTC-USD"
DEFAULT_ORDER_ASSET_QUANTITY = "0.000001"


class CryptoAPITradingV2:
    def __init__(self, api_key: str, base64_private_key: str):
        if not api_key:
            raise ValueError("Missing ROBINHOOD_API_KEY")
        if not base64_private_key:
            raise ValueError("Missing ROBINHOOD_BASE64_PRIVATE_KEY")

        self.api_key = api_key
        private_key_seed = base64.b64decode(base64_private_key)
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
        body = {
            "client_order_id": client_order_id,
            "side": side,
            "type": order_type,
            "symbol": symbol,
            f"{order_type}_order_config": order_config,
        }
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


def env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y"}


def get_order_config_from_env() -> Dict[str, str]:
    raw_config = os.environ.get("ROBINHOOD_ORDER_CONFIG_JSON")
    if raw_config:
        try:
            parsed_config = json.loads(raw_config)
        except json.JSONDecodeError as error:
            raise ValueError("ROBINHOOD_ORDER_CONFIG_JSON must be valid JSON.") from error

        if not isinstance(parsed_config, dict):
            raise ValueError("ROBINHOOD_ORDER_CONFIG_JSON must decode to an object.")

        return {str(key): str(value) for key, value in parsed_config.items()}

    order_config = {
        "asset_quantity": os.environ.get(
            "ROBINHOOD_ORDER_ASSET_QUANTITY", DEFAULT_ORDER_ASSET_QUANTITY
        )
    }

    limit_price = os.environ.get("ROBINHOOD_ORDER_LIMIT_PRICE")
    if limit_price:
        order_config["limit_price"] = limit_price

    stop_price = os.environ.get("ROBINHOOD_ORDER_STOP_PRICE")
    if stop_price:
        order_config["stop_price"] = stop_price

    return order_config


def main() -> None:
    api_key = os.environ.get("ROBINHOOD_API_KEY", "")
    base64_private_key = os.environ.get("ROBINHOOD_BASE64_PRIVATE_KEY", "")

    if not api_key or not base64_private_key:
        raise ValueError(
            "Set ROBINHOOD_API_KEY and ROBINHOOD_BASE64_PRIVATE_KEY before running."
        )

    api_trading_client = CryptoAPITradingV2(api_key=api_key, base64_private_key=base64_private_key)

    accounts = api_trading_client.get_accounts()
    if not isinstance(accounts, dict) or "results" not in accounts or not accounts["results"]:
        raise RuntimeError(f"Unable to fetch accounts: {accounts}")

    account_number = accounts["results"][0]["account_number"]
    print(f"Using account: ****{account_number[-4:]}")

    order_symbol = os.environ.get("ROBINHOOD_ORDER_SYMBOL", DEFAULT_ORDER_SYMBOL).upper()
    order_side = os.environ.get("ROBINHOOD_ORDER_SIDE", "buy").lower()
    order_type = os.environ.get("ROBINHOOD_ORDER_TYPE", "market").lower()
    order_config = get_order_config_from_env()

    if order_side not in {"buy", "sell"}:
        raise ValueError("ROBINHOOD_ORDER_SIDE must be 'buy' or 'sell'.")

    trading_pairs = api_trading_client.get_trading_pairs(order_symbol)
    print(f"Loaded trading pairs: {len(trading_pairs)}")

    asset_quantity = order_config.get("asset_quantity")
    if asset_quantity:
        estimated_price = api_trading_client.get_estimated_price(
            symbol=order_symbol, side="both", quantity=asset_quantity
        )
        print("Estimated price:")
        print(json.dumps(estimated_price, indent=2))
    else:
        print("Estimated price skipped: order config has no asset_quantity.")

    print("Prepared order:")
    print(
        json.dumps(
            {
                "side": order_side,
                "type": order_type,
                "symbol": order_symbol,
                f"{order_type}_order_config": order_config,
            },
            indent=2,
        )
    )

    if env_flag_enabled("ROBINHOOD_PLACE_REAL_ORDER"):
        order_response = api_trading_client.place_order(
            account_number=account_number,
            client_order_id=str(uuid.uuid4()),
            side=order_side,
            order_type=order_type,
            symbol=order_symbol,
            order_config=order_config,
        )
        print("Order response:")
        print(json.dumps(order_response, indent=2))
    else:
        print(
            "Dry run mode: set ROBINHOOD_PLACE_REAL_ORDER=true to place a live order."
        )


if __name__ == "__main__":
    main()
