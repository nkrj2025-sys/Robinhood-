import unittest

from robinhood_api_trading_v2 import (
    DEFAULT_ASSET_QUANTITY,
    build_order_config,
    build_order_payload,
    get_first_account_number,
    parse_args,
    should_place_real_order,
)


class OrderConfigTests(unittest.TestCase):
    def test_builds_market_order_config_with_asset_quantity(self):
        config = build_order_config("market", asset_quantity="0.000001")

        self.assertEqual(config, {"asset_quantity": "0.000001"})

    def test_builds_limit_order_config(self):
        config = build_order_config(
            "limit",
            asset_quantity="0.01",
            limit_price="50000",
            time_in_force="gtc",
        )

        self.assertEqual(
            config,
            {
                "asset_quantity": "0.01",
                "limit_price": "50000",
                "time_in_force": "gtc",
            },
        )

    def test_market_order_requires_exactly_one_quantity_field(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            build_order_config(
                "market",
                asset_quantity="0.000001",
                quote_amount="1.00",
            )

    def test_order_config_json_must_be_an_object(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            build_order_config("market", order_config_json='["not", "object"]')


class OrderPayloadTests(unittest.TestCase):
    def test_builds_normalized_payload(self):
        payload = build_order_payload(
            client_order_id="order-1",
            side="BUY",
            order_type="MARKET",
            symbol="btc-usd",
            order_config={"asset_quantity": DEFAULT_ASSET_QUANTITY},
        )

        self.assertEqual(
            payload,
            {
                "client_order_id": "order-1",
                "side": "buy",
                "type": "market",
                "symbol": "BTC-USD",
                "market_order_config": {
                    "asset_quantity": DEFAULT_ASSET_QUANTITY,
                },
            },
        )

    def test_rejects_invalid_side(self):
        with self.assertRaisesRegex(ValueError, "side must be"):
            build_order_payload(
                client_order_id="order-1",
                side="hold",
                order_type="market",
                symbol="BTC-USD",
                order_config={"asset_quantity": "0.000001"},
            )


class AccountResponseTests(unittest.TestCase):
    def test_gets_first_account_number(self):
        account_number = get_first_account_number(
            {"results": [{"account_number": "123456789"}]}
        )

        self.assertEqual(account_number, "123456789")

    def test_rejects_missing_accounts(self):
        with self.assertRaisesRegex(RuntimeError, "Unable to fetch accounts"):
            get_first_account_number({"results": []})


class CliTests(unittest.TestCase):
    def test_dry_run_overrides_live_order_env(self):
        args = parse_args(["--dry-run"])

        self.assertFalse(
            should_place_real_order(args, {"ROBINHOOD_PLACE_REAL_ORDER": "true"})
        )

    def test_place_real_order_flag_enables_live_order(self):
        args = parse_args(["--place-real-order"])

        self.assertTrue(should_place_real_order(args, {}))


if __name__ == "__main__":
    unittest.main()
