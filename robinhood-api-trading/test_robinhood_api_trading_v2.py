import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("robinhood_api_trading_v2.py")
SPEC = importlib.util.spec_from_file_location("robinhood_api_trading_v2", MODULE_PATH)
assert SPEC is not None
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class OrderPlacementSafetyTests(unittest.TestCase):
    def test_parse_args_defaults_to_small_dry_run_quantity(self):
        args = module.parse_args([])

        self.assertFalse(args.place)
        self.assertEqual(args.asset_quantity, "0.000001")
        self.assertIsNone(args.quote_amount)

    def test_live_order_requires_explicit_size(self):
        args = module.parse_args(["--place"])

        with self.assertRaisesRegex(ValueError, "Pass --asset-quantity or --quote-amount"):
            module.build_order_config(
                order_type=args.order_type,
                asset_quantity=args.asset_quantity,
                quote_amount=args.quote_amount,
                limit_price=args.limit_price,
                time_in_force=args.time_in_force,
            )

    def test_build_order_config_rejects_conflicting_sizes(self):
        with self.assertRaisesRegex(ValueError, "Pass only one"):
            module.build_order_config(
                order_type="market",
                asset_quantity="0.1",
                quote_amount="10",
                limit_price=None,
                time_in_force=None,
            )

    def test_limit_order_requires_limit_price(self):
        with self.assertRaisesRegex(ValueError, "Limit orders require"):
            module.build_order_config(
                order_type="limit",
                asset_quantity="0.1",
                quote_amount=None,
                limit_price=None,
                time_in_force=None,
            )

    def test_build_order_body_uses_order_type_specific_config_key(self):
        order_body = module.CryptoAPITradingV2.build_order_body(
            client_order_id="order-id",
            side="buy",
            order_type="market",
            symbol="BTC-USD",
            order_config={"asset_quantity": "0.000001"},
        )

        self.assertEqual(
            order_body,
            {
                "client_order_id": "order-id",
                "side": "buy",
                "type": "market",
                "symbol": "BTC-USD",
                "market_order_config": {"asset_quantity": "0.000001"},
            },
        )

    def test_live_order_gates_require_account_env_and_confirmation(self):
        with self.assertRaisesRegex(ValueError, "account-number"):
            module.validate_live_order_gates(
                place=True,
                account_number=None,
                confirmation=module.LIVE_ORDER_CONFIRMATION,
                environ={"ROBINHOOD_PLACE_REAL_ORDER": "true"},
            )

        with self.assertRaisesRegex(ValueError, "ROBINHOOD_PLACE_REAL_ORDER"):
            module.validate_live_order_gates(
                place=True,
                account_number="acct",
                confirmation=module.LIVE_ORDER_CONFIRMATION,
                environ={},
            )

        with self.assertRaisesRegex(ValueError, "confirm-live-order"):
            module.validate_live_order_gates(
                place=True,
                account_number="acct",
                confirmation="yes",
                environ={"ROBINHOOD_PLACE_REAL_ORDER": "true"},
            )

        module.validate_live_order_gates(
            place=True,
            account_number="acct",
            confirmation=module.LIVE_ORDER_CONFIRMATION,
            environ={"ROBINHOOD_PLACE_REAL_ORDER": "true"},
        )


if __name__ == "__main__":
    unittest.main()
