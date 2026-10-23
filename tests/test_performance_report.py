import unittest
from datetime import datetime, timezone
from performance_report import Client, ApiError, board_summary, resolved_contributions, resolved_question, collect, is_due


class PerformanceTest(unittest.TestCase):
    def test_aggregate_entries_have_no_user(self):
        data = board_summary({"entries": [{"user": None, "score": 30}, {"user": {"id": 9}, "score": -3, "rank": 4}]}, 9)
        self.assertEqual(data["own_entry"]["score"], -3)

    def test_refresh_daily_or_on_new_resolved_ids(self):
        previous = {"started_at_utc": "2026-10-23T08:00:00+00:00", "status": "completed", "resolution_signature": [1]}
        now = datetime(2026, 10, 23, 9, tzinfo=timezone.utc)
        self.assertFalse(is_due(previous, [1], now))
        self.assertTrue(is_due(previous, [1, 2], now))
        self.assertTrue(is_due(previous, [1], datetime(2026, 10, 23, 15, tzinfo=timezone.utc)))
        previous["status"] = "failed"
        self.assertFalse(is_due(previous, [1, 2], now))
    def test_not_listed_is_unknown_not_zero(self):
        data = board_summary({"entries": [{"user": {"id": 8}, "score": 12}]}, 9)
        self.assertEqual(data["entry_status"], "not_listed")
        self.assertIsNone(data["own_entry"])

    def test_official_zero_is_preserved(self):
        data = board_summary({"entries": [{"user": {"id": 9}, "score": 0, "rank": 3}]}, 9)
        self.assertEqual(data["own_entry"]["score"], 0)
        self.assertEqual(data["own_entry"]["rank"], 3)
        self.assertIsNone(data["prize_payment_confirmed"])

    def test_live_and_annulled_excluded_from_analysis(self):
        rows = [{"question_resolution": x, "secret": "not exported"} for x in (None, "", "annulled", "ambiguous", "no", "0")]
        self.assertEqual(len(resolved_contributions(rows)), 2)
        self.assertNotIn("secret", resolved_contributions(rows)[0])

    def test_live_forecasts_never_exported(self):
        result = resolved_question({"question": {"id": 1, "status": "open", "my_forecasts": {"latest": {"probability_yes": .1}}}}, 1)
        self.assertNotIn("last_forecast", result)

    def test_error_never_exports_response_or_token(self):
        class Response:
            status_code = 403
            text = "private credentials"
        with self.assertRaisesRegex(ApiError, "^http_403$"):
            Client("secret", lambda *a, **k: Response()).read("users/me/")

    def test_identity_failure_is_explicit(self):
        class Response:
            status_code = 401
        result = collect("secret", lambda *a, **k: Response())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["api_get_calls"], 1)
        self.assertEqual(result["llm_calls"], 0)


if __name__ == "__main__":
    unittest.main()
