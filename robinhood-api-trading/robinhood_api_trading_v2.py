import argparse
import base64
import datetime
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import urllib.parse
import uuid


DEFAULT_ASSET_QUANTITY = "0.000001"
ROBINHOOD_BASE_URL = "https://trading.robinhood.com"
VALID_ORDER_SIDES = {"buy", "sell"}
VALID_ORDER_TYPES = {"market", "limit"}


def _normalize_required_value(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def build_order_config(
    order_type: str,
    *,
    asset_quantity: Optional[str] = None,
    quote_amount: Optional[str] = None,
    limit_price: Optional[str] = None,
    time_in_force: Optional[str] = None,
    order_config_json: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_order_type = order_type.lower().strip()
    if normalized_order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"order_type must be one of {sorted(VALID_ORDER_TYPES)}, got {order_type!r}"
        )

    if order_config_json:
        try:
            parsed_config = json.loads(order_config_json)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid order config JSON: {error}") from error
        if not isinstance(parsed_config, dict):
            raise ValueError("order_config_json must decode to a JSON object")
        return parsed_config

    if normalized_order_type == "market":
        quantity_fields = {
            "asset_quantity": asset_quantity,
            "quote_amount": quote_amount,
        }
        configured_fields = {
            key: value for key, value in quantity_fields.items() if value is not None
        }
        if len(configured_fields) != 1:
            raise ValueError(
                "Market orders require exactly one of asset_quantity or quote_amount"
            )
        return configured_fields

    if quote_amount is not None:
        raise ValueError("Limit orders must use asset_quantity, not quote_amount")
    if asset_quantity is None:
        raise ValueError("Limit orders require asset_quantity")
    if limit_price is None:
        raise ValueError("Limit orders require limit_price")

    limit_order_config: Dict[str, Any] = {
        "asset_quantity": asset_quantity,
        "limit_price": limit_price,
    }
    if time_in_force:
        limit_order_config["time_in_force"] = time_in_force
    return limit_order_config


def build_order_payload(
    *,
    client_order_id: str,
    side: str,
    order_type: str,
    symbol: str,
    order_config: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_side = side.lower().strip()
    normalized_order_type = order_type.lower().strip()
    normalized_symbol = _normalize_required_value("symbol", symbol).upper()
    normalized_client_order_id = _normalize_required_value(
        "client_order_id", client_order_id
    )

    if normalized_side not in VALID_ORDER_SIDES:
        raise ValueError(
            f"side must be one of {sorted(VALID_ORDER_SIDES)}, got {side!r}"
        )
    if normalized_order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"order_type must be one of {sorted(VALID_ORDER_TYPES)}, got {order_type!r}"
        )
    if not isinstance(order_config, dict) or not order_config:
        raise ValueError("order_config must be a non-empty dictionary")

    return {
        "client_order_id": normalized_client_order_id,
        "side": normalized_side,
        "type": normalized_order_type,
        "symbol": normalized_symbol,
        f"{normalized_order_type}_order_config": order_config,
    }


def get_first_account_number(accounts_response: Any) -> str:
    if (
        not isinstance(accounts_response, dict)
        or not isinstance(accounts_response.get("results"), list)
        or not accounts_response["results"]
    ):
        raise RuntimeError(f"Unable to fetch accounts: {accounts_response}")

    account_number = accounts_response["results"][0].get("account_number")
    if not account_number:
        raise RuntimeError(f"Unable to find account_number: {accounts_response}")
    return account_number


def mask_account_number(account_number: Optional[str]) -> Optional[str]:
    if not account_number:
        return None
    return f"****{account_number[-4:]}"


class CryptoAPITradingV2:
    def __init__(
        self,
        api_key: str,
        base64_private_key: str,
        *,
        base_url: str = ROBINHOOD_BASE_URL,
        session: Optional[Any] = None,
    ):
        if not api_key:
            raise ValueError("Missing ROBINHOOD_API_KEY")
        if not base64_private_key:
            raise ValueError("Missing ROBINHOOD_BASE64_PRIVATE_KEY")

        import requests
        from nacl.signing import SigningKey

        self.api_key = api_key
        private_key_seed = base64.b64decode(base64_private_key)
        self.private_key = SigningKey(private_key_seed)
        self.base_url = base_url
        self.session = session or requests.Session()
        self._requests = requests

    @classmethod
    def from_env(cls) -> "CryptoAPITradingV2":
        return cls(
            api_key=os.environ.get("ROBINHOOD_API_KEY", ""),
            base64_private_key=os.environ.get("ROBINHOOD_BASE64_PRIVATE_KEY", ""),
        )

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
                response = self.session.post(
                    url, headers=headers, data=body, timeout=10
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            try:
                return response.json()
            except ValueError:
                return {"status_code": response.status_code, "error": response.text}
        except self._requests.RequestException as error:
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
        order_config: Dict[str, Any],
    ) -> Any:
        body = build_order_payload(
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


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or place a Robinhood Crypto API order."
    )
    parser.add_argument("--symbol", default="BTC-USD", help="Trading pair, e.g. BTC-USD")
    parser.add_argument("--side", default="buy", choices=sorted(VALID_ORDER_SIDES))
    parser.add_argument(
        "--order-type", default="market", choices=sorted(VALID_ORDER_TYPES)
    )
    parser.add_argument(
        "--asset-quantity",
        help=f"Asset quantity to trade. Defaults to {DEFAULT_ASSET_QUANTITY}.",
    )
    parser.add_argument("--quote-amount", help="Quote currency amount for market orders")
    parser.add_argument("--limit-price", help="Limit price for limit orders")
    parser.add_argument(
        "--time-in-force",
        default="gtc",
        help="Limit order time in force. Default: gtc",
    )
    parser.add_argument(
        "--order-config-json",
        help="Advanced raw JSON object for the API order config",
    )
    parser.add_argument(
        "--account-number",
        help="Account number to use. If omitted for live orders, the first account is used.",
    )
    parser.add_argument(
        "--client-order-id", help="Client order UUID. Defaults to uuid4()."
    )
    parser.add_argument(
        "--place-real-order",
        action="store_true",
        help="Submit the order to Robinhood instead of only printing a preview.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force preview mode even when ROBINHOOD_PLACE_REAL_ORDER=true.",
    )
    args = parser.parse_args(argv)

    if args.place_real_order and args.dry_run:
        parser.error("--place-real-order and --dry-run cannot be used together")
    if args.order_config_json and any(
        [args.asset_quantity, args.quote_amount, args.limit_price]
    ):
        parser.error(
            "--order-config-json cannot be combined with quantity or price options"
        )
    return args


def should_place_real_order(args: argparse.Namespace, env: Mapping[str, str]) -> bool:
    if args.dry_run:
        return False
    return (
        args.place_real_order
        or env.get("ROBINHOOD_PLACE_REAL_ORDER", "").lower() == "true"
    )


def build_order_preview(
    *,
    account_number: Optional[str],
    payload: Dict[str, Any],
    live_order_enabled: bool,
) -> Dict[str, Any]:
    query_params = CryptoAPITradingV2.get_query_params(
        {"account_number": account_number or "<resolved before live order>"}
    )
    return {
        "mode": "live" if live_order_enabled else "dry_run",
        "account_number": mask_account_number(account_number),
        "endpoint": f"/api/v2/crypto/trading/orders/{query_params}",
        "body": payload,
    }


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    place_real_order = should_place_real_order(args, os.environ)
    asset_quantity = args.asset_quantity

    if not asset_quantity and not args.quote_amount and not args.order_config_json:
        asset_quantity = DEFAULT_ASSET_QUANTITY

    order_config = build_order_config(
        args.order_type,
        asset_quantity=asset_quantity,
        quote_amount=args.quote_amount,
        limit_price=args.limit_price,
        time_in_force=args.time_in_force,
        order_config_json=args.order_config_json,
    )
    client_order_id = args.client_order_id or str(uuid.uuid4())
    payload = build_order_payload(
        client_order_id=client_order_id,
        side=args.side,
        order_type=args.order_type,
        symbol=args.symbol,
        order_config=order_config,
    )

    if not place_real_order:
        print("Dry run mode: no order submitted.")
        print(
            json.dumps(
                build_order_preview(
                    account_number=args.account_number,
                    payload=payload,
                    live_order_enabled=False,
                ),
                indent=2,
            )
        )
        print(
            "Pass --place-real-order or set ROBINHOOD_PLACE_REAL_ORDER=true to submit."
        )
        return

    api_trading_client = CryptoAPITradingV2.from_env()
    account_number = args.account_number or get_first_account_number(
        api_trading_client.get_accounts()
    )
    print(
        json.dumps(
            build_order_preview(
                account_number=account_number,
                payload=payload,
                live_order_enabled=True,
            ),
            indent=2,
        )
    )
    order_response = api_trading_client.place_order(
        account_number=account_number,
        client_order_id=client_order_id,
        side=args.side,
        order_type=args.order_type,
        symbol=args.symbol,
        order_config=order_config,
    )
    print("Order response:")
    print(json.dumps(order_response, indent=2))


if __name__ == "__main__":
    main()
