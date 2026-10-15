from pathlib import Path
import tempfile
import unittest

from theme_tracker import attach_prior_ranks, average, build_snapshot, leader_is_most_of_the_move, render_html
from themes_catalog import THEMES, unique_tickers, validate_catalog


REQUIRED = [
    "GPUs",
    "CPUs",
    "Memory",
    "MLCC",
    "Semi Testing",
    "Robotics",
    "Agentic AI",
    "Edge AI",
    "Routers",
    "GLP-1",
]


def quote(symbol: str, today: float) -> dict:
    return {
        "description": symbol,
        "exchange": "NASDAQ",
        "close": 10.0,
        "url": f"https://example.test/{symbol}",
        "today": today,
        "w1": today,
        "m1": today,
        "m3": today,
        "m6": today,
        "ytd": today,
    }


class ThemeTapeTests(unittest.TestCase):
    def test_catalog_covers_the_requested_themes(self):
        validate_catalog()
        names = {row["name"] for row in THEMES}
        for name in REQUIRED:
            self.assertIn(name, names)
        self.assertGreaterEqual(len(THEMES), 50)
        self.assertEqual(len(unique_tickers()), len(set(unique_tickers())))

    def test_average_waits_for_three_prints(self):
        self.assertIsNone(average([1.0, None]))
        self.assertEqual(average([1.0, None, 3.0, 5.0]), 3.0)

    def test_thin_basket_stays_blank_and_names_the_leader(self):
        themes = [{
            "id": "gpus",
            "name": "GPUs",
            "lane": "Semis",
            "blurb": "chips",
            "tickers": ["NVDA", "AMD", "DEAD"],
            "etf": None,
        }]
        snapshot = build_snapshot(themes, {"NVDA": quote("NVDA", 4.0), "AMD": quote("AMD", -2.0)}, "2026-09-22")
        row = snapshot["themes"][0]
        self.assertEqual(row["unquoted"], ["DEAD"])
        self.assertIsNone(row["today"])
        self.assertEqual(row["leader"]["symbol"], "NVDA")
        self.assertEqual(row["green"], 1)
        self.assertEqual(row["prints"], 2)

    def test_equal_weight_uses_only_printed_names(self):
        themes = [{
            "id": "gpus",
            "name": "GPUs",
            "lane": "Semis",
            "blurb": "chips <script>",
            "tickers": ["NVDA", "AMD", "AVGO"],
            "etf": "SMH",
        }]
        quotes = {"NVDA": quote("NVDA", 3.0), "AMD": quote("AMD", 6.0), "AVGO": quote("AVGO", 9.0)}
        snapshot = build_snapshot(themes, quotes, "2026-09-22")
        self.assertEqual(snapshot["themes"][0]["today"], 6.0)
        html = render_html(snapshot)
        self.assertIn("Theme Tape", html)
        self.assertIn("GB Market Terminal", html)
        self.assertIn('aria-current="page"', html)
        self.assertIn("liquid.html", html)
        self.assertIn('aria-current="page">Tape</a>', html)
        self.assertNotIn("<script>", html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
        self.assertIn("\\u003c", html)

    def test_leader_flag_when_the_rest_do_not_carry_the_move(self):
        self.assertTrue(leader_is_most_of_the_move([("A", 20.0), ("B", 2.0), ("C", 2.0)], "A"))
        self.assertTrue(leader_is_most_of_the_move([("A", 10.0), ("B", -1.0), ("C", -1.0)], "A"))
        self.assertFalse(leader_is_most_of_the_move([("A", 10.0), ("B", 9.0), ("C", 8.0)], "A"))
        self.assertFalse(leader_is_most_of_the_move([("A", 5.0)], "A"))

    def test_prior_rank_comes_from_the_previous_tape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "theme_tracker_2026-10-12.csv").write_text(
                "theme,today\nBrazil,1.0\nHomebuilders,3.0\nWearable AI,\n",
                encoding="utf-8",
            )
            (root / "theme_tracker_2026-10-13.csv").write_text(
                "theme,today\nBrazil,9.0\nHomebuilders,1.0\nWearable AI,0.2\n",
                encoding="utf-8",
            )
            snapshot = {
                "as_of": "2026-10-13",
                "themes": [
                    {"name": "Brazil"},
                    {"name": "Homebuilders"},
                    {"name": "Wearable AI"},
                ],
            }
            attach_prior_ranks(snapshot, root)
        self.assertEqual(snapshot["themes"][0]["prior_rank"], 2)
        self.assertEqual(snapshot["themes"][1]["prior_rank"], 1)
        self.assertIsNone(snapshot["themes"][2]["prior_rank"])


if __name__ == "__main__":
    unittest.main()
