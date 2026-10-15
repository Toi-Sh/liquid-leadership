import unittest

from crowding import GROUPS, GROUP_SERIES, badge, compare_rows, history_points, place_words, range_place


def cot_row(iso, oi, **nets):
    row = {"report_date_as_yyyy_mm_dd": iso, "open_interest_all": oi}
    for (key, _label, _color, _short), spec in zip(GROUP_SERIES, GROUPS):
        net = nets.get(key, 0)
        row[spec[1]] = net if net > 0 else 0
        row[spec[2]] = -net if net < 0 else 0
    return row


class CrowdingTest(unittest.TestCase):
    def test_range_place(self):
        self.assertEqual(range_place(0, [0, 10, -10]), 50)
        self.assertEqual(range_place(10, [10, 0]), 100)
        self.assertEqual(range_place(-10, [-10, 0]), 0)
        self.assertEqual(range_place(3, [3, 3]), 50)
        self.assertEqual(range_place(50, [50] + [0] * 155 + [1000]), 100)

    def test_extremes(self):
        self.assertIsNone(place_words("Dealers", 11))
        self.assertIsNone(place_words("Dealers", 89))
        self.assertEqual(place_words("Dealers", 10), "Dealers near the short extreme")
        self.assertEqual(place_words("Dealers", 90), "Dealers near the long extreme")
        text, kind = badge([("Leveraged funds", 4), ("Asset managers", 96), ("Dealers", 40)])
        self.assertEqual(kind, "warn")
        self.assertIn("Leveraged funds near the short extreme", text)
        self.assertIn("Asset managers near the long extreme", text)
        self.assertNotIn("Dealers", text)
        self.assertEqual(badge([("Leveraged funds", 50)]), ("No group is at an extreme", "quiet"))

    def test_history_is_share_of_open_interest_oldest_first(self):
        points = history_points([
            cot_row("2026-10-06", 100, dealers=30, lev=-10),
            cot_row("2026-09-29", 200, dealers=0),
        ])
        self.assertEqual([point["d"] for point in points], ["2026-09-29", "2026-10-06"])
        self.assertEqual(points[1]["dealers"], 30.0)
        self.assertEqual(points[1]["lev"], -10.0)
        self.assertEqual(points[0]["dealers"], 0.0)

    def test_compare_rows_use_share_of_open_interest(self):
        groups = [{"name": label, "net": 0} for _key, label, _color, _short in GROUP_SERIES]
        groups[2]["net"] = -25
        rows = compare_rows([{"key": "spy", "oi": 100, "groups": groups}])
        self.assertEqual(rows[2]["label"], "Leveraged")
        self.assertEqual(rows[2]["spy"], -25.0)


if __name__ == "__main__":
    unittest.main()
