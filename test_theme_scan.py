import unittest

import pandas as pd

from theme_scan import ThemeScanSettings, ma_is_rising, passes_quote_rules, select_group_leaders, top_themes


def quote_row(**overrides) -> dict:
    row = {
        "name": "AAA",
        "description": "Aaa",
        "exchange": "NASDAQ",
        "industry": "Semiconductors",
        "close": 20.0,
        "change": 1.0,
        "volume": 2_000_000,
        "SMA10": 18.0,
        "SMA20": 17.0,
        "SMA10|1W": 16.0,
        "earnings_per_share_diluted_yoy_growth_fq": 50.0,
        "earnings_per_share_diluted_yoy_growth_ttm": 10.0,
        "total_revenue_yoy_growth_fq": 45.0,
        "total_revenue_yoy_growth_ttm": 10.0,
        "Perf.1M": 12.0,
    }
    row.update(overrides)
    return row


class ThemeScanTests(unittest.TestCase):
    def test_top_themes_keep_the_board_and_a_new_riser(self):
        leaders = pd.DataFrame({
            "industry": ["Semis", "Semis", "Semis", "Semis", "Software", "Software", "Software", "Hardware", "Hardware"],
            "is_top_1m": [True] * 9,
        })
        prior = pd.DataFrame({
            "industry": ["Semis", "Semis", "Semis", "Semis", "Software", "Software", "Software"],
            "is_top_1m": [True] * 7,
        })
        themes = top_themes(leaders, prior, count=2)
        self.assertEqual(themes[:2], ["Semis", "Software"])
        self.assertIn("Hardware", themes)

    def test_quote_rules_reject_a_wide_day_and_weak_growth(self):
        frame = pd.DataFrame([
            quote_row(name="PASS"),
            quote_row(name="WIDE", change=8.0),
            quote_row(name="THIN", volume=500_000),
            quote_row(name="CHEAP", close=0.8),
            quote_row(name="UNDER", close=10, SMA10=12),
            quote_row(name="FLAT", earnings_per_share_diluted_yoy_growth_fq=10),
        ])
        kept = passes_quote_rules(frame, ThemeScanSettings())
        self.assertEqual(kept["name"].tolist(), ["PASS"])

    def test_missing_quarterly_growth_uses_the_trailing_figure(self):
        frame = pd.DataFrame([
            quote_row(
                earnings_per_share_diluted_yoy_growth_fq=None,
                earnings_per_share_diluted_yoy_growth_ttm=44,
                total_revenue_yoy_growth_fq=None,
                total_revenue_yoy_growth_ttm=41,
            )
        ])
        kept = passes_quote_rules(frame, ThemeScanSettings())
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept.iloc[0]["earn_yoy"], 44)

    def test_group_leader_is_the_best_one_month_name(self):
        frame = pd.DataFrame([
            quote_row(name="LAGGARD", **{"Perf.1M": 5}),
            quote_row(name="LEADER", **{"Perf.1M": 30}),
            quote_row(name="OTHER", industry="Software", **{"Perf.1M": 8}),
        ])
        leaders = select_group_leaders(frame)
        self.assertEqual(set(leaders["name"]), {"LEADER", "OTHER"})

    def test_a_rising_average_needs_enough_history(self):
        rising = pd.Series(range(40), dtype=float)
        flat = pd.Series([10.0] * 40)
        self.assertTrue(ma_is_rising(rising, 10, 5))
        self.assertFalse(ma_is_rising(flat, 10, 5))
        self.assertFalse(ma_is_rising(rising.iloc[:8], 10, 5))


if __name__ == "__main__":
    unittest.main()
