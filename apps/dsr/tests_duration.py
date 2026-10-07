from decimal import Decimal

from django.test import SimpleTestCase

from apps.dsr.duration import format_hm, parse_hours


class DurationTest(SimpleTestCase):
    def test_parses_every_supported_shape(self):
        cases = {
            "1.5": "1.50", "1,5": "1.50", "2": "2.00", "90m": "1.50", "90 min": "1.50",
            "1h": "1.00", "1h30": "1.50", "1h 30m": "1.50", "1:30": "1.50", "45m": "0.75",
            "20 minutes": "0.33", "2 hrs": "2.00", " 1H 15M ": "1.25", "0.25": "0.25",
        }
        for text, want in cases.items():
            self.assertEqual(parse_hours(text), Decimal(want), text)

    def test_blank_is_none_and_garbage_raises(self):
        self.assertIsNone(parse_hours("  "))
        for bad in ("abc", "h", "1h h", "-1", "1:2:3", "m30", "1.5.5", "three hours"):
            with self.assertRaises(ValueError, msg=bad):
                parse_hours(bad)

    def test_format_and_round_trip(self):
        self.assertEqual([format_hm(x) for x in ("1.5", "0.75", "2", "0.33", 0, None)], ["1h 30m", "45m", "2h", "20m", "0m", ""])
        for text in ("20m", "1h 30m", "7m", "2h", "59m"):
            self.assertEqual(format_hm(parse_hours(text)), text)
