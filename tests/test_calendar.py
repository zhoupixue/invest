import datetime as dt
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_daily import eligible

class CalendarTests(unittest.TestCase):
    def at(self,s):return eligible(dt.datetime.fromisoformat(s))
    def test_weekend_and_holiday(self):
        self.assertIsNone(self.at('2026-10-11T22:17:00+00:00'))
        self.assertIsNone(self.at('2026-12-25T22:17:00+00:00'))
    def test_summer_and_winter(self):
        self.assertEqual(str(self.at('2026-10-09T22:17:00+00:00')),'2026-10-09')
        self.assertEqual(str(self.at('2026-12-24T22:17:00+00:00')),'2026-12-24')
        self.assertIsNone(self.at('2026-12-23T21:30:00+00:00'))
    def test_early_close(self):
        self.assertEqual(str(self.at('2026-11-27T19:17:00+00:00')),'2026-11-27')
        self.assertIsNone(self.at('2026-11-27T18:30:00+00:00'))
