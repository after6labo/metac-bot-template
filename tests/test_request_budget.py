import json
import tempfile
import unittest
from pathlib import Path
from request_budget import DailyRequestBudget, BudgetExhausted


class BudgetTests(unittest.TestCase):
    def test_reservation_survives_restart_and_blocks_before_extra_call(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            first = DailyRequestBudget(path, limit=2, today='2026-09-24')
            first.reserve()
            second = DailyRequestBudget(path, limit=2, today='2026-09-24')
            second.reserve()
            with self.assertRaises(BudgetExhausted):
                second.reserve()
            self.assertEqual(json.loads(path.read_text())['requests_reserved'], 2)

    def test_new_utc_day_resets_and_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            old = DailyRequestBudget(path, limit=1, today='2026-09-23')
            old.reserve()
            new = DailyRequestBudget(path, limit=1, today='2026-09-24')
            self.assertEqual(new.remaining, 1)
            path.write_text('{broken')
            with self.assertRaises(ValueError):
                DailyRequestBudget(path)

    def test_provider_quota_failure_blocks_rest_of_day(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            budget = DailyRequestBudget(path, today='2026-09-24')
            budget.reserve()
            budget.block()
            resumed = DailyRequestBudget(path, today='2026-09-24')
            self.assertEqual(resumed.remaining, 0)
            with self.assertRaises(BudgetExhausted):
                resumed.reserve()


if __name__ == '__main__':
    unittest.main()
