import unittest
from datetime import datetime, timezone
from performance_report import Client, ApiError, board_summary, resolved_contributions, resolved_question, resolved_posts, collect, is_due


class PerformanceTest(unittest.TestCase):
    def test_many_results_need_one_batch_request(self):
        class FakeClient:
            calls = 0
            def read(self, path, params):
                self.calls += 1
                return {"results": [{"id": i} for i in range(60)]}
        client = FakeClient()
        self.assertEqual(len(resolved_posts(client, 123, set(range(60)))), 60)
        self.assertEqual(client.calls, 1)

    def test_missing_result_is_explicit_not_empty_success(self):
        class FakeClient:
            def read(self, path, params): return {"results": []}
        with self.assertRaisesRegex(ApiError, "resolved_contribution_posts_missing"):
            resolved_posts(FakeClient(), 123, {9})
    def test_rate_limit_stops_all_later_requests_and_records_wait(self):
        class Response:
            status_code = 429
            headers = {"Retry-After": "600"}
        client = Client("secret", lambda *a, **k: Response(), sleep=lambda s: None)
        with self.assertRaisesRegex(ApiError, "http_429"):
            client.read("a")
        with self.assertRaisesRegex(ApiError, "http_429_paused"):
            client.read("b")
        self.assertEqual(client.calls, 1)
        self.assertIsNotNone(client.retry_not_before_utc)

    def test_cooldown_wins_over_schema_refresh(self):
        previous = {"schema_version": 1, "retry_not_before_utc": "2026-10-24T00:00:00+00:00"}
        self.assertFalse(is_due(previous, [], datetime(2026, 10, 23, tzinfo=timezone.utc)))

    def test_requests_are_spaced(self):
        waits = []
        class Response:
            status_code = 200
            def json(self): return {}
        client = Client("secret", lambda *a, **k: Response(), sleep=waits.append)
        client.read("a")
        client.read("b")
        self.assertEqual(waits, [3.2])
    def test_aggregate_entries_have_no_user(self):
        data = board_summary({"entries": [{"user": None, "score": 30}, {"user": {"id": 9}, "score": -3, "rank": 4}]}, 9)
        self.assertEqual(data["own_entry"]["score"], -3)

    def test_refresh_daily_or_on_new_resolved_ids(self):
        previous = {"schema_version": 2, "started_at_utc": "2026-10-23T08:00:00+00:00", "status": "completed", "resolution_signature": [1]}
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

    def test_resolved_forecast_uses_official_serializer_shape(self):
        result = resolved_question({"question": {"id": 1, "status": "resolved", "type": "binary", "resolution": "yes", "my_forecasts": {"latest": {"forecast_values": [.2, .8]}, "history": [{}]}}}, 1)
        self.assertEqual(result["last_forecast"]["forecast_values"], [.2, .8])
        self.assertEqual(result["forecast_count"], 1)

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
