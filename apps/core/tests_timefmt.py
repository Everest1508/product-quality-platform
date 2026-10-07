from datetime import datetime, time

from django.test import SimpleTestCase

from apps.core.timefmt import t12


class T12Test(SimpleTestCase):
    def test_reads_like_a_clock(self):
        self.assertEqual(t12(time(0, 5)), "12:05 AM")
        self.assertEqual(t12(time(9, 0)), "9:00 AM")
        self.assertEqual(t12(time(12, 0)), "12:00 PM")
        self.assertEqual(t12(time(18, 30)), "6:30 PM")
        self.assertEqual(t12(datetime(2026, 10, 7, 23, 59)), "11:59 PM")
