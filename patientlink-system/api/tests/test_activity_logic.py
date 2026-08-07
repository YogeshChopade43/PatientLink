import unittest
from datetime import datetime, date

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from main import is_course_active_on_date  # noqa: E402


class ActivityLogicTests(unittest.TestCase):
    def test_strict_five_day_window(self):
        start = datetime(2026, 3, 1, 10, 30, 0)
        self.assertTrue(is_course_active_on_date(start, 5, date(2026, 3, 1)))
        self.assertTrue(is_course_active_on_date(start, 5, date(2026, 3, 5)))
        self.assertFalse(is_course_active_on_date(start, 5, date(2026, 3, 6)))

    def test_invalid_values(self):
        self.assertFalse(is_course_active_on_date(None, 5, date(2026, 3, 1)))
        self.assertFalse(is_course_active_on_date(datetime(2026, 3, 1), 0, date(2026, 3, 1)))


if __name__ == "__main__":
    unittest.main()
