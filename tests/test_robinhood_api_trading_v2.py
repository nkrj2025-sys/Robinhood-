import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "robinhood-api-trading"
    / "robinhood_api_trading_v2.py"
)

spec = importlib.util.spec_from_file_location("robinhood_api_trading_v2", MODULE_PATH)
robinhood_api_trading_v2 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(robinhood_api_trading_v2)


class OrderHelperTests(unittest.TestCase):
    def test_build_market_order_config_requires_one_quantity_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            robinhood_api_trading_v2.build_market_order_config(None, None)

        with self.assertRaisesRegex(ValueError, "exactly one"):
            robinhood_api_trading_v2.build_market_order_config("0.1", "5")

    def test_build_market_order_config_accepts_asset_quantity(self) -> None:
        self.assertEqual(
            robinhood_api_trading_v2.build_market_order_config("0.000001", None),
            {"asset_quantity": "0.000001"},
        )

    def test_build_market_order_config_accepts_quote_amount(self) -> None:
        self.assertEqual(
            robinhood_api_trading_v2.build_market_order_config(None, "5"),
            {"quote_amount": "5"},
        )

    def test_build_order_body_uses_order_type_specific_config_key(self) -> None:
        body = robinhood_api_trading_v2.build_order_body(
            client_order_id="order-id",
            side="buy",
            order_type="market",
            symbol="BTC-USD",
            order_config={"asset_quantity": "0.000001"},
        )

        self.assertEqual(
            body,
            {
                "client_order_id": "order-id",
                "side": "buy",
                "type": "market",
                "symbol": "BTC-USD",
                "market_order_config": {"asset_quantity": "0.000001"},
            },
        )

    def test_find_trading_pair_returns_requested_symbol(self) -> None:
        trading_pair = robinhood_api_trading_v2.find_trading_pair(
            [{"symbol": "ETH-USD"}, {"symbol": "BTC-USD"}], "BTC-USD"
        )

        self.assertEqual(trading_pair, {"symbol": "BTC-USD"})

    def test_find_trading_pair_raises_when_symbol_is_missing(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "BTC-USD"):
            robinhood_api_trading_v2.find_trading_pair(
                [{"symbol": "ETH-USD"}], "BTC-USD"
            )

    def test_place_order_posts_account_scoped_body(self) -> None:
        client = robinhood_api_trading_v2.CryptoAPITradingV2.__new__(
            robinhood_api_trading_v2.CryptoAPITradingV2
        )
        client.make_api_request = mock.Mock(return_value={"id": "order-id"})

        response = client.place_order(
            account_number="acct-123",
            client_order_id="order-id",
            side="buy",
            order_type="market",
            symbol="BTC-USD",
            order_config={"asset_quantity": "0.000001"},
        )

        self.assertEqual(response, {"id": "order-id"})
        client.make_api_request.assert_called_once()
        method, path, body_json = client.make_api_request.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(
            path, "/api/v2/crypto/trading/orders/?account_number=acct-123"
        )
        self.assertEqual(
            json.loads(body_json),
            {
                "client_order_id": "order-id",
                "side": "buy",
                "type": "market",
                "symbol": "BTC-USD",
                "market_order_config": {"asset_quantity": "0.000001"},
            },
        )

    def test_should_place_real_order_requires_flag_and_environment(self) -> None:
        args = robinhood_api_trading_v2.parse_args(["--place-real-order"])

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(robinhood_api_trading_v2.should_place_real_order(args))

        with mock.patch.dict(os.environ, {"ROBINHOOD_PLACE_REAL_ORDER": "true"}):
            self.assertTrue(robinhood_api_trading_v2.should_place_real_order(args))

        args = robinhood_api_trading_v2.parse_args([])
        with mock.patch.dict(os.environ, {"ROBINHOOD_PLACE_REAL_ORDER": "true"}):
            self.assertFalse(robinhood_api_trading_v2.should_place_real_order(args))

    def test_main_dry_run_does_not_construct_client_with_credentials(self) -> None:
        env = {
            "ROBINHOOD_API_KEY": "test-key",
            "ROBINHOOD_BASE64_PRIVATE_KEY": "test-private-key",
        }

        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(
                robinhood_api_trading_v2, "CryptoAPITradingV2"
            ) as client_class:
                with mock.patch.object(sys, "stdout", new=io.StringIO()) as output:
                    robinhood_api_trading_v2.main(
                        [
                            "--client-order-id",
                            "order-id",
                            "--asset-quantity",
                            "0.000001",
                        ]
                    )

        client_class.assert_not_called()
        self.assertIn("Dry run mode", output.getvalue())


if __name__ == "__main__":
    unittest.main()
