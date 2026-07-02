import base64
from collections import deque
from dataclasses import dataclass
import datetime
import json
import os
from decimal import Decimal, InvalidOperation
import time
from typing import Any, Deque, Dict, List, Optional, Tuple
import urllib.parse
import uuid

import requests
from nacl.signing import SigningKey


@dataclass
class StrategyConfig:
    symbol: str = "BTC-USD"
    lookback_ticks: int = 8
    momentum_threshold_pct: Decimal = Decimal("0.20")
    trade_notional_usd: Decimal = Decimal("25")
    max_position_asset: Decimal = Decimal("0.01")
    max_iterations: int = 50
    poll_interval_seconds: int = 20
    place_real_order: bool = False


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


def _to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        if value is None:
            return default
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _extract_mid_price(best_bid_ask_response: Dict[str, Any], symbol: str) -> Optional[Decimal]:
    results = best_bid_ask_response.get("results", []) if isinstance(best_bid_ask_response, dict) else []
    if not isinstance(results, list):
        return None

    for row in results:
        if not isinstance(row, dict) or row.get("symbol") != symbol:
            continue

        bid = _to_decimal(
            row.get("bid_inclusive_of_sell_spread")
            or row.get("bid")
            or row.get("bid_price")
        )
        ask = _to_decimal(
            row.get("ask_inclusive_of_buy_spread")
            or row.get("ask")
            or row.get("ask_price")
        )
        if bid > 0 and ask > 0:
            return (bid + ask) / Decimal("2")
    return None


def _extract_quantity(holdings_response: Dict[str, Any], asset_code: str) -> Decimal:
    results = holdings_response.get("results", []) if isinstance(holdings_response, dict) else []
    if not isinstance(results, list):
        return Decimal("0")

    for row in results:
        if not isinstance(row, dict) or row.get("asset_code") != asset_code:
            continue
        return _to_decimal(
            row.get("total_quantity")
            or row.get("quantity")
            or row.get("available_quantity")
            or row.get("quantity_available_for_trading"),
            default=Decimal("0"),
        )
    return Decimal("0")


def _extract_buying_power(account_row: Dict[str, Any]) -> Decimal:
    candidates = [
        account_row.get("buying_power"),
        account_row.get("cash_buying_power"),
        account_row.get("available_cash"),
        account_row.get("cash_available_for_withdrawal"),
    ]

    for item in candidates:
        if isinstance(item, dict):
            for key in ("amount", "value", "quantity"):
                amount = _to_decimal(item.get(key), default=Decimal("-1"))
                if amount >= 0:
                    return amount
        else:
            amount = _to_decimal(item, default=Decimal("-1"))
            if amount >= 0:
                return amount
    return Decimal("0")


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        return max(int(raw), minimum)
    except ValueError:
        return default


def _load_strategy_config() -> StrategyConfig:
    return StrategyConfig(
        symbol=os.environ.get("ROBINHOOD_SYMBOL", "BTC-USD"),
        lookback_ticks=_env_int("ROBINHOOD_LOOKBACK_TICKS", default=8, minimum=2),
        momentum_threshold_pct=_to_decimal(os.environ.get("ROBINHOOD_MOMENTUM_THRESHOLD_PCT", "0.20")),
        trade_notional_usd=_to_decimal(os.environ.get("ROBINHOOD_TRADE_NOTIONAL_USD", "25")),
        max_position_asset=_to_decimal(os.environ.get("ROBINHOOD_MAX_POSITION_ASSET", "0.01")),
        max_iterations=_env_int("ROBINHOOD_MAX_ITERATIONS", default=50, minimum=1),
        poll_interval_seconds=_env_int("ROBINHOOD_POLL_INTERVAL_SECONDS", default=20, minimum=1),
        place_real_order=os.environ.get("ROBINHOOD_PLACE_REAL_ORDER", "").lower() == "true",
    )


def _derive_signal(price_window: Deque[Decimal], threshold_pct: Decimal) -> str:
    if len(price_window) < 2 or price_window[0] <= 0:
        return "hold"
    momentum_pct = ((price_window[-1] - price_window[0]) / price_window[0]) * Decimal("100")
    if momentum_pct >= threshold_pct:
        return "buy"
    if momentum_pct <= (threshold_pct * Decimal("-1")):
        return "sell"
    return "hold"


def _round_asset_quantity(asset_quantity: Decimal) -> str:
    return str(asset_quantity.quantize(Decimal("0.00000001")))


def main() -> None:
    api_key = os.environ.get("ROBINHOOD_API_KEY", "")
    base64_private_key = os.environ.get("ROBINHOOD_BASE64_PRIVATE_KEY", "")

    if not api_key or not base64_private_key:
        raise ValueError(
            "Set ROBINHOOD_API_KEY and ROBINHOOD_BASE64_PRIVATE_KEY before running."
        )

    api_trading_client = CryptoAPITradingV2(api_key=api_key, base64_private_key=base64_private_key)
    config = _load_strategy_config()

    accounts = api_trading_client.get_accounts()
    if not isinstance(accounts, dict) or "results" not in accounts or not accounts["results"]:
        raise RuntimeError(f"Unable to fetch accounts: {accounts}")

    account_row = accounts["results"][0]
    account_number = account_row["account_number"]
    buying_power_usd = _extract_buying_power(account_row)
    asset_code = config.symbol.split("-")[0]

    print(f"Using account: ****{account_number[-4:]}")
    print(
        f"Strategy config => symbol={config.symbol}, lookback={config.lookback_ticks}, "
        f"threshold={config.momentum_threshold_pct}%"
    )
    print(
        "Execution mode => "
        + ("LIVE ORDERS ENABLED" if config.place_real_order else "DRY RUN (no live orders)")
    )

    trading_pairs = api_trading_client.get_trading_pairs(config.symbol)
    print(f"Loaded trading pairs: {len(trading_pairs)}")

    prices: Deque[Decimal] = deque(maxlen=config.lookback_ticks)
    for iteration in range(1, config.max_iterations + 1):
        best_bid_ask = api_trading_client.get_best_bid_ask(config.symbol)
        mid_price = _extract_mid_price(best_bid_ask, config.symbol)
        if mid_price is None or mid_price <= 0:
            print(f"[{iteration}] Unable to determine market price: {best_bid_ask}")
            time.sleep(config.poll_interval_seconds)
            continue

        prices.append(mid_price)
        signal = _derive_signal(prices, config.momentum_threshold_pct)
        print(f"[{iteration}] Mid={mid_price} Signal={signal}")

        if signal == "hold":
            time.sleep(config.poll_interval_seconds)
            continue

        holdings_response = api_trading_client.get_holdings(account_number, asset_code)
        asset_position = _extract_quantity(holdings_response, asset_code)

        if signal == "buy":
            asset_quantity = config.trade_notional_usd / mid_price
            if buying_power_usd < config.trade_notional_usd:
                print(
                    f"[{iteration}] Skip BUY: buying power ${buying_power_usd} below "
                    f"${config.trade_notional_usd}"
                )
            elif asset_position + asset_quantity > config.max_position_asset:
                print(
                    f"[{iteration}] Skip BUY: position limit exceeded. "
                    f"Current={asset_position}, Max={config.max_position_asset}"
                )
            else:
                order_config = {"asset_quantity": _round_asset_quantity(asset_quantity)}
                if config.place_real_order:
                    order_response = api_trading_client.place_order(
                        account_number=account_number,
                        client_order_id=str(uuid.uuid4()),
                        side="buy",
                        order_type="market",
                        symbol=config.symbol,
                        order_config=order_config,
                    )
                    print(f"[{iteration}] BUY order response: {json.dumps(order_response)}")
                    buying_power_usd -= config.trade_notional_usd
                else:
                    print(f"[{iteration}] DRY RUN BUY => {order_config}")

        elif signal == "sell":
            asset_quantity = min(config.trade_notional_usd / mid_price, asset_position)
            if asset_quantity <= 0:
                print(f"[{iteration}] Skip SELL: no {asset_code} position available")
            else:
                order_config = {"asset_quantity": _round_asset_quantity(asset_quantity)}
                if config.place_real_order:
                    order_response = api_trading_client.place_order(
                        account_number=account_number,
                        client_order_id=str(uuid.uuid4()),
                        side="sell",
                        order_type="market",
                        symbol=config.symbol,
                        order_config=order_config,
                    )
                    print(f"[{iteration}] SELL order response: {json.dumps(order_response)}")
                else:
                    print(f"[{iteration}] DRY RUN SELL => {order_config}")

        time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    main()
