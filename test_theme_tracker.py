import unittest

from theme_tracker import average, build_snapshot, render_html
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
        self.assertIn('aria-current="page"', html)
        self.assertIn("index.html#liquid-title", html)
        self.assertIn("F10</kbd> Tape</a>", html)
        self.assertNotIn("<script>", html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
        self.assertIn("\\u003c", html)


if __name__ == "__main__":
    unittest.main()
