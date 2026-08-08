import unittest
from contextlib import redirect_stdout
from io import StringIO

from market_screeners.screeners.option_analysis import (
    OptionChainAnalyzer,
    OptionSnapshot,
    print_table,
)


class OptionAnalysisClassificationTests(unittest.TestCase):
    def test_classify_pcr(self):
        self.assertEqual(OptionChainAnalyzer.classify_pcr(1.3), "green")
        self.assertEqual(OptionChainAnalyzer.classify_pcr(0.7), "red")
        self.assertEqual(OptionChainAnalyzer.classify_pcr(1.0), "yellow")
        self.assertEqual(OptionChainAnalyzer.classify_pcr(None), "yellow")

    def test_classify_bmi(self):
        self.assertEqual(OptionChainAnalyzer.classify_bmi(6.0), "green")
        self.assertEqual(OptionChainAnalyzer.classify_bmi(-6.0), "red")
        self.assertEqual(OptionChainAnalyzer.classify_bmi(1.0), "yellow")
        self.assertEqual(OptionChainAnalyzer.classify_bmi(None), "yellow")

    def test_classify_iv_skew(self):
        self.assertEqual(OptionChainAnalyzer.classify_iv_skew(2.0), "green")
        self.assertEqual(OptionChainAnalyzer.classify_iv_skew(-2.0), "red")
        self.assertEqual(OptionChainAnalyzer.classify_iv_skew(0.0), "yellow")
        self.assertEqual(OptionChainAnalyzer.classify_iv_skew(None), "yellow")

    def test_classify_hotspot(self):
        self.assertEqual(OptionChainAnalyzer.classify_hotspot("P"), "green")
        self.assertEqual(OptionChainAnalyzer.classify_hotspot("C"), "red")
        self.assertEqual(OptionChainAnalyzer.classify_hotspot(None), "yellow")

    def test_classify_spot_vs_max_pain(self):
        self.assertEqual(OptionChainAnalyzer.classify_spot_vs_max_pain(90, 95, 105), "green")
        self.assertEqual(OptionChainAnalyzer.classify_spot_vs_max_pain(110, 95, 105), "red")
        self.assertEqual(OptionChainAnalyzer.classify_spot_vs_max_pain(100, 95, 105), "yellow")
        self.assertEqual(OptionChainAnalyzer.classify_spot_vs_max_pain(None, 95, 105), "yellow")


class OptionAnalysisTablePrintingTests(unittest.TestCase):
    def test_print_table_renders_ticker_and_error_rows(self):
        good = OptionSnapshot(
            ticker="AAA",
            spot=100.0,
            atm_strike=100.0,
            max_call_oi_strike=105.0,
            max_put_oi_strike=95.0,
            pcr=1.5,
            iv_skew_pct=2.0,
            hotspot_strike=100.0,
            hotspot_side="C",
            hotspot_ratio=1.2,
            bmi_pct=3.0,
            max_pain_low=95.0,
            max_pain_high=105.0,
            atr=2.5,
            atr_percentile=60.0,
        )
        errored = OptionSnapshot(ticker="BBB", error="No option expirations found")

        output = StringIO()
        with redirect_stdout(output):
            print_table([good, errored])

        rendered = output.getvalue()
        self.assertIn("AAA", rendered)
        self.assertIn("BBB", rendered)
        self.assertIn("error: No option expirations found", rendered)

    def test_print_table_emits_ansi_colors_even_without_a_real_terminal(self):
        # Regression test: print_table used to silently drop all color
        # when its output wasn't a real terminal (e.g. when captured for
        # the HTML export), because rich auto-detects "not a tty" and
        # disables ANSI codes.
        snap = OptionSnapshot(
            ticker="AAA",
            spot=100.0,
            atm_strike=100.0,
            max_call_oi_strike=105.0,
            max_put_oi_strike=95.0,
            pcr=1.5,
            iv_skew_pct=2.0,
            hotspot_strike=100.0,
            hotspot_side="C",
            hotspot_ratio=1.2,
            bmi_pct=3.0,
            max_pain_low=95.0,
            max_pain_high=105.0,
            atr=2.5,
            atr_percentile=60.0,
        )

        output = StringIO()
        with redirect_stdout(output):
            print_table([snap])

        self.assertIn("\033[", output.getvalue())


if __name__ == "__main__":
    unittest.main()
