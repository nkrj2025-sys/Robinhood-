import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "robinhood-api-trading"
    / "robinhood_api_trading_v2.py"
)
SPEC = importlib.util.spec_from_file_location("robinhood_api_trading_v2", MODULE_PATH)
robinhood_v2 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(robinhood_v2)


class OrderPlacementSafetyTests(unittest.TestCase):
    def test_build_order_config_defaults_market_asset_quantity(self):
        order_config = robinhood_v2.build_order_config(
            order_type="market",
            asset_quantity="0.000001",
            quote_amount=None,
            limit_price=None,
            time_in_force=None,
        )

        self.assertEqual(order_config, {"asset_quantity": "0.000001"})

    def test_build_order_config_rejects_ambiguous_size(self):
        with self.assertRaisesRegex(ValueError, "only one"):
            robinhood_v2.build_order_config(
                order_type="market",
                asset_quantity="0.000001",
                quote_amount="1.00",
                limit_price=None,
                time_in_force=None,
            )

    def test_build_order_config_requires_limit_price(self):
        with self.assertRaisesRegex(ValueError, "Limit orders require"):
            robinhood_v2.build_order_config(
                order_type="limit",
                asset_quantity="0.000001",
                quote_amount=None,
                limit_price=None,
                time_in_force="gtc",
            )

    def test_validate_live_order_gates_allows_dry_run(self):
        robinhood_v2.validate_live_order_gates(
            place=False,
            account_number=None,
            confirmation=None,
            environ={},
        )

    def test_validate_live_order_gates_requires_account(self):
        with self.assertRaisesRegex(ValueError, "account"):
            robinhood_v2.validate_live_order_gates(
                place=True,
                account_number=None,
                confirmation=robinhood_v2.LIVE_ORDER_CONFIRMATION,
                environ={"ROBINHOOD_PLACE_REAL_ORDER": "true"},
            )

    def test_validate_live_order_gates_requires_env_opt_in(self):
        with self.assertRaisesRegex(ValueError, "ROBINHOOD_PLACE_REAL_ORDER=true"):
            robinhood_v2.validate_live_order_gates(
                place=True,
                account_number="abc123",
                confirmation=robinhood_v2.LIVE_ORDER_CONFIRMATION,
                environ={},
            )

    def test_validate_live_order_gates_requires_confirmation_phrase(self):
        with self.assertRaisesRegex(ValueError, "confirm-live-order"):
            robinhood_v2.validate_live_order_gates(
                place=True,
                account_number="abc123",
                confirmation="yes",
                environ={"ROBINHOOD_PLACE_REAL_ORDER": "true"},
            )

    def test_build_order_body_uses_order_type_config_key(self):
        body = robinhood_v2.CryptoAPITradingV2.build_order_body(
            client_order_id="order-1",
            side="buy",
            order_type="market",
            symbol="BTC-USD",
            order_config={"asset_quantity": "0.000001"},
        )

        self.assertEqual(
            body,
            {
                "client_order_id": "order-1",
                "side": "buy",
                "type": "market",
                "symbol": "BTC-USD",
                "market_order_config": {"asset_quantity": "0.000001"},
            },
        )


if __name__ == "__main__":
    unittest.main()
