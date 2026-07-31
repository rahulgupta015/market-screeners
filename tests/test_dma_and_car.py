import unittest
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from unittest.mock import patch

import pandas as pd

from market_screeners.model.calc import Calc
from market_screeners.model.display import Display
from market_screeners.model.market_universe import load_market_universe
from market_screeners.model.ticker import Ticker
from market_screeners.service.compute_service import compute_car, get_zone, is_car_breakout, is_dma_breakout, scan_all
from market_screeners.service.display_service import (
    GREEN,
    PURPLE,
    RED,
    YELLOW,
    car_color,
    format_row,
    print_results,
    rsi_color,
    shift_color,
)


class DmaAndCarTests(unittest.TestCase):
    def test_zone_codes_preserve_zone_rules(self):
        self.assertEqual(
            get_zone(120, 100, 90, 80, {50: 99, 100: 89, 200: 79}),
            "B++",
        )
        self.assertEqual(
            get_zone(104, 103, 102, 95, {50: 101, 100: 102.5, 200: 94}),
            "B+",
        )
        self.assertEqual(
            get_zone(80, 90, 95, 100, {50: 92, 100: 91, 200: 99}),
            "B-",
        )
        self.assertEqual(
            get_zone(70, 80, 85, 90, {50: 81, 100: 86, 200: 91}),
            "B--",
        )
        self.assertEqual(
            get_zone(100, 90, 95, 80, {50: 89, 100: 94, 200: 79}),
            "U",
        )

    def test_compute_car_scores_longest_increasing_tail(self):
        dates = pd.date_range("2026-01-01", periods=5, freq="D")
        prices = pd.Series([10, 9, 8, 9, 10], index=dates)

        self.assertEqual(compute_car(prices, dates[0]), 3)

    def test_market_universe_creates_ticker_models(self):
        universe = load_market_universe()

        self.assertIn("AAPL", universe)
        self.assertIsInstance(universe["AAPL"], Ticker)
        self.assertEqual(universe["AAPL"].asset_type, "stock")

    def test_scan_all_returns_calc_records(self):
        tickers = [Ticker("AAA"), Ticker("BBB")]
        expected = [Calc(ticker=ticker) for ticker in tickers]

        with patch("market_screeners.service.compute_service.compute_ticker", side_effect=expected) as compute:
            actual = scan_all(tickers)

        self.assertEqual(actual, expected)
        self.assertEqual(compute.call_count, 2)

    def test_breakout_rules_do_not_depend_on_zone(self):
        calc = Calc(
            ticker=Ticker("TEST"),
            cmp=103,
            dma_50=102,
            dma_100=101,
            dma_200=100,
            shift_pct=3,
            zone="U",
            car=5,
        )

        self.assertTrue(is_dma_breakout(calc))
        self.assertTrue(is_car_breakout(calc))

    def test_car_breakout_requires_car_score_of_five(self):
        calc = Calc(
            ticker=Ticker("TEST"),
            cmp=103,
            dma_50=102,
            dma_100=101,
            dma_200=100,
            shift_pct=3,
            car=4,
        )

        self.assertTrue(is_dma_breakout(calc))
        self.assertFalse(is_car_breakout(calc))

    def test_display_formatting_returns_display_model(self):
        calc = Calc(
            ticker=Ticker("TEST"),
            cmp=42.5,
            zone="B+",
            high_date=pd.Timestamp(date(2026, 7, 15)),
            low_date=pd.Timestamp(date(2026, 4, 2)),
        )

        row = format_row(calc)

        self.assertIsInstance(row, Display)
        self.assertEqual(row["Stock"], "TEST")
        self.assertEqual(row["CMP"], "42.5")
        self.assertEqual(row["52W High"], "07-15-26")
        self.assertEqual(row["52W Low"], "04-02-26")

    def test_breakout_tables_allow_overlap(self):
        dma_only = Calc(ticker=Ticker("DMA"), dma_bo=True, shift_pct=2)
        car_only = Calc(ticker=Ticker("CAR"), car_bo=True, car=6, shift_pct=3)
        both = Calc(ticker=Ticker("BOTH"), dma_bo=True, car_bo=True, car=7, shift_pct=1)
        other = Calc(ticker=Ticker("OTHER"))
        output = StringIO()

        with redirect_stdout(output):
            print_results([dma_only, car_only, both, other])

        rendered = output.getvalue()
        self.assertLess(rendered.index("DMA Breakout"), rendered.index("CAR Breakout"))
        self.assertLess(rendered.index("CAR Breakout"), rendered.index("Others"))
        self.assertIn("Total: 4 symbols (2 DMA breakouts, 2 CAR breakouts, 1 others)", rendered)

    def test_color_thresholds(self):
        self.assertEqual(rsi_color(25), PURPLE)
        self.assertEqual(rsi_color(40), GREEN)
        self.assertEqual(rsi_color(65), YELLOW)
        self.assertEqual(rsi_color(66), RED)
        self.assertEqual(shift_color(10), GREEN)
        self.assertEqual(shift_color(10.01), PURPLE)
        self.assertEqual(shift_color(-10), YELLOW)
        self.assertEqual(shift_color(-10.01), RED)
        self.assertEqual(car_color(1), RED)
        self.assertEqual(car_color(2), YELLOW)
        self.assertEqual(car_color(5), GREEN)
        self.assertEqual(car_color(10), PURPLE)


if __name__ == "__main__":
    unittest.main()
