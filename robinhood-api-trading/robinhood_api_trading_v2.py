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
    stop_loss_pct: Decimal = Decimal("1.00")
    take_profit_pct: Decimal = Decimal("1.50")
    max_loss_usd: Decimal = Decimal("20")
    max_trades_per_run: int = 6
    cooldown_iterations: int = 2


@dataclass
class RuntimeConfig:
    strategy: StrategyConfig
    connectivity_check_only: bool = False
    trade_audit_log_path: str = "logs/trade_audit.jsonl"


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


def _load_dotenv(dotenv_path: str = ".env") -> None:
    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as dotenv_file:
        for raw_line in dotenv_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def _load_strategy_config() -> RuntimeConfig:
    strategy = StrategyConfig(
        symbol=os.environ.get("ROBINHOOD_SYMBOL", "BTC-USD"),
        lookback_ticks=_env_int("ROBINHOOD_LOOKBACK_TICKS", default=8, minimum=2),
        momentum_threshold_pct=_to_decimal(os.environ.get("ROBINHOOD_MOMENTUM_THRESHOLD_PCT", "0.20")),
        trade_notional_usd=_to_decimal(os.environ.get("ROBINHOOD_TRADE_NOTIONAL_USD", "25")),
        max_position_asset=_to_decimal(os.environ.get("ROBINHOOD_MAX_POSITION_ASSET", "0.01")),
        max_iterations=_env_int("ROBINHOOD_MAX_ITERATIONS", default=50, minimum=1),
        poll_interval_seconds=_env_int("ROBINHOOD_POLL_INTERVAL_SECONDS", default=20, minimum=1),
        place_real_order=os.environ.get("ROBINHOOD_PLACE_REAL_ORDER", "").lower() == "true",
        stop_loss_pct=_to_decimal(os.environ.get("ROBINHOOD_STOP_LOSS_PCT", "1.00")),
        take_profit_pct=_to_decimal(os.environ.get("ROBINHOOD_TAKE_PROFIT_PCT", "1.50")),
        max_loss_usd=_to_decimal(os.environ.get("ROBINHOOD_MAX_LOSS_USD", "20")),
        max_trades_per_run=_env_int("ROBINHOOD_MAX_TRADES_PER_RUN", default=6, minimum=1),
        cooldown_iterations=_env_int("ROBINHOOD_COOLDOWN_ITERATIONS", default=2, minimum=0),
    )
    return RuntimeConfig(
        strategy=strategy,
        connectivity_check_only=os.environ.get("ROBINHOOD_CONNECTIVITY_CHECK_ONLY", "").lower() == "true",
        trade_audit_log_path=os.environ.get("ROBINHOOD_TRADE_AUDIT_LOG_PATH", "logs/trade_audit.jsonl"),
    )


def _load_validated_credentials() -> Tuple[str, str]:
    api_key = os.environ.get("ROBINHOOD_API_KEY", "").strip()
    base64_private_key = os.environ.get("ROBINHOOD_BASE64_PRIVATE_KEY", "").strip()

    if not api_key or not base64_private_key:
        raise ValueError(
            "Missing credentials. Set ROBINHOOD_API_KEY and ROBINHOOD_BASE64_PRIVATE_KEY "
            "via environment or a local .env file."
        )

    if api_key.startswith("ADD YOUR") or base64_private_key.startswith("ADD YOUR"):
        raise ValueError("Detected placeholder credentials. Replace with real secret values.")

    try:
        private_key_seed = base64.b64decode(base64_private_key)
    except Exception as error:  # pylint: disable=broad-exception-caught
        raise ValueError("ROBINHOOD_BASE64_PRIVATE_KEY is not valid base64.") from error

    if len(private_key_seed) != 32:
        raise ValueError(
            "ROBINHOOD_BASE64_PRIVATE_KEY must decode to a 32-byte Ed25519 seed."
        )

    return api_key, base64_private_key


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


def _percent_move(current_price: Decimal, reference_price: Decimal) -> Decimal:
    if reference_price <= 0:
        return Decimal("0")
    return ((current_price - reference_price) / reference_price) * Decimal("100")


def _append_audit_log(log_path: str, event: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(log_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    record = {
        "timestamp_utc": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        "event": event,
        "payload": payload,
    }
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, default=str) + "\n")


def main() -> None:
    _load_dotenv()
    api_key, base64_private_key = _load_validated_credentials()

    api_trading_client = CryptoAPITradingV2(api_key=api_key, base64_private_key=base64_private_key)
    runtime = _load_strategy_config()
    config = runtime.strategy

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

    if runtime.connectivity_check_only:
        print("Connectivity check success. Exiting because ROBINHOOD_CONNECTIVITY_CHECK_ONLY=true.")
        _append_audit_log(
            runtime.trade_audit_log_path,
            "connectivity_check",
            {"status": "success", "symbol": config.symbol},
        )
        return

    trading_pairs = api_trading_client.get_trading_pairs(config.symbol)
    print(f"Loaded trading pairs: {len(trading_pairs)}")

    prices: Deque[Decimal] = deque(maxlen=config.lookback_ticks)
    managed_position_qty = Decimal("0")
    managed_avg_entry_price = Decimal("0")
    realized_pnl_usd = Decimal("0")
    trades_executed = 0
    cooldown_until_iteration = 0

    for iteration in range(1, config.max_iterations + 1):
        best_bid_ask = api_trading_client.get_best_bid_ask(config.symbol)
        mid_price = _extract_mid_price(best_bid_ask, config.symbol)
        if mid_price is None or mid_price <= 0:
            print(f"[{iteration}] Unable to determine market price: {best_bid_ask}")
            _append_audit_log(
                runtime.trade_audit_log_path,
                "market_data_unavailable",
                {"iteration": iteration, "symbol": config.symbol, "response": best_bid_ask},
            )
            time.sleep(config.poll_interval_seconds)
            continue

        prices.append(mid_price)
        signal = _derive_signal(prices, config.momentum_threshold_pct)
        unrealized_pnl_usd = (mid_price - managed_avg_entry_price) * managed_position_qty
        strategy_pnl_usd = realized_pnl_usd + unrealized_pnl_usd
        print(
            f"[{iteration}] Mid={mid_price} Signal={signal} "
            f"PnL=${strategy_pnl_usd.quantize(Decimal('0.01'))}"
        )

        if strategy_pnl_usd <= (config.max_loss_usd * Decimal("-1")):
            print(
                f"[{iteration}] Trading halted: max loss reached "
                f"(${strategy_pnl_usd.quantize(Decimal('0.01'))} <= -${config.max_loss_usd})."
            )
            _append_audit_log(
                runtime.trade_audit_log_path,
                "risk_halt_max_loss",
                {
                    "iteration": iteration,
                    "strategy_pnl_usd": str(strategy_pnl_usd.quantize(Decimal("0.01"))),
                    "max_loss_usd": str(config.max_loss_usd),
                },
            )
            break

        if trades_executed >= config.max_trades_per_run:
            print(
                f"[{iteration}] Trading halted: max trades per run reached "
                f"({trades_executed}/{config.max_trades_per_run})."
            )
            _append_audit_log(
                runtime.trade_audit_log_path,
                "risk_halt_max_trades",
                {
                    "iteration": iteration,
                    "trades_executed": trades_executed,
                    "max_trades_per_run": config.max_trades_per_run,
                },
            )
            break

        if managed_position_qty > 0 and managed_avg_entry_price > 0:
            move_pct = _percent_move(mid_price, managed_avg_entry_price)
            if move_pct <= (config.stop_loss_pct * Decimal("-1")):
                signal = "sell"
                print(f"[{iteration}] Stop-loss triggered at {move_pct.quantize(Decimal('0.01'))}%.")
            elif move_pct >= config.take_profit_pct:
                signal = "sell"
                print(f"[{iteration}] Take-profit triggered at {move_pct.quantize(Decimal('0.01'))}%.")

        if signal == "hold" or iteration < cooldown_until_iteration:
            if iteration < cooldown_until_iteration:
                print(
                    f"[{iteration}] Cooling down. Next trade allowed at iteration "
                    f"{cooldown_until_iteration}."
                )
                _append_audit_log(
                    runtime.trade_audit_log_path,
                    "trade_skipped_cooldown",
                    {
                        "iteration": iteration,
                        "signal": signal,
                        "cooldown_until_iteration": cooldown_until_iteration,
                    },
                )
            else:
                _append_audit_log(
                    runtime.trade_audit_log_path,
                    "trade_skipped_hold",
                    {"iteration": iteration, "signal": signal},
                )
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
                _append_audit_log(
                    runtime.trade_audit_log_path,
                    "trade_blocked_buying_power",
                    {
                        "iteration": iteration,
                        "signal": "buy",
                        "mid_price": str(mid_price),
                        "buying_power_usd": str(buying_power_usd),
                        "required_notional_usd": str(config.trade_notional_usd),
                    },
                )
            elif asset_position + asset_quantity > config.max_position_asset:
                print(
                    f"[{iteration}] Skip BUY: position limit exceeded. "
                    f"Current={asset_position}, Max={config.max_position_asset}"
                )
                _append_audit_log(
                    runtime.trade_audit_log_path,
                    "trade_blocked_position_limit",
                    {
                        "iteration": iteration,
                        "signal": "buy",
                        "mid_price": str(mid_price),
                        "asset_position": str(asset_position),
                        "requested_asset_quantity": str(asset_quantity),
                        "max_position_asset": str(config.max_position_asset),
                    },
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
                    execution_mode = "live"
                else:
                    print(f"[{iteration}] DRY RUN BUY => {order_config}")
                    order_response = {"dry_run": True}
                    execution_mode = "dry_run"
                _append_audit_log(
                    runtime.trade_audit_log_path,
                    "trade_executed",
                    {
                        "iteration": iteration,
                        "side": "buy",
                        "symbol": config.symbol,
                        "mid_price": str(mid_price),
                        "signal": signal,
                        "order_config": order_config,
                        "execution_mode": execution_mode,
                        "strategy_pnl_usd": str(strategy_pnl_usd.quantize(Decimal("0.01"))),
                        "response": order_response,
                    },
                )
                previous_notional = managed_avg_entry_price * managed_position_qty
                managed_position_qty += asset_quantity
                if managed_position_qty > 0:
                    managed_avg_entry_price = (previous_notional + (asset_quantity * mid_price)) / managed_position_qty
                trades_executed += 1
                cooldown_until_iteration = iteration + config.cooldown_iterations + 1

        elif signal == "sell":
            sell_cap = managed_position_qty if managed_position_qty > 0 else asset_position
            asset_quantity = min(config.trade_notional_usd / mid_price, sell_cap)
            if asset_quantity <= 0:
                print(f"[{iteration}] Skip SELL: no {asset_code} position available")
                _append_audit_log(
                    runtime.trade_audit_log_path,
                    "trade_blocked_no_position",
                    {
                        "iteration": iteration,
                        "signal": "sell",
                        "asset_code": asset_code,
                        "asset_position": str(asset_position),
                        "managed_position_qty": str(managed_position_qty),
                    },
                )
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
                    execution_mode = "live"
                else:
                    print(f"[{iteration}] DRY RUN SELL => {order_config}")
                    order_response = {"dry_run": True}
                    execution_mode = "dry_run"
                if managed_avg_entry_price > 0:
                    realized_pnl_usd += (mid_price - managed_avg_entry_price) * asset_quantity
                _append_audit_log(
                    runtime.trade_audit_log_path,
                    "trade_executed",
                    {
                        "iteration": iteration,
                        "side": "sell",
                        "symbol": config.symbol,
                        "mid_price": str(mid_price),
                        "signal": signal,
                        "order_config": order_config,
                        "execution_mode": execution_mode,
                        "strategy_pnl_usd": str(strategy_pnl_usd.quantize(Decimal("0.01"))),
                        "response": order_response,
                    },
                )
                managed_position_qty = max(managed_position_qty - asset_quantity, Decimal("0"))
                if managed_position_qty == 0:
                    managed_avg_entry_price = Decimal("0")
                trades_executed += 1
                cooldown_until_iteration = iteration + config.cooldown_iterations + 1

        time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    main()
