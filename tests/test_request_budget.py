import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from request_budget import DailyRequestBudget


class BudgetTests(unittest.TestCase):
    def test_more_than_fifty_responses_do_not_impose_a_local_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            state = DailyRequestBudget(Path(folder) / 'budget.json')
            for _ in range(51):
                state.record_response(7)
            self.assertTrue(state.can_request)
            self.assertEqual(state.data['successful_responses'], 51)
            self.assertEqual(state.data['observed_tokens'], 357)
            self.assertNotIn('requests_reserved', state.data)

    def test_failure_is_diagnostic_not_a_consumed_request(self):
        with tempfile.TemporaryDirectory() as folder:
            state = DailyRequestBudget(Path(folder) / 'budget.json')
            state.record_failure(ValueError('do not log this payload'))
            self.assertTrue(state.can_request)
            self.assertEqual(state.data['failed_invocations'], 1)
            self.assertEqual(state.data['successful_responses'], 0)
            self.assertEqual(state.data['observed_tokens'], 0)
            self.assertNotIn('do not log', str(state.data))
            self.assertNotIn('requests_reserved', state.data)

    def test_legacy_counter_and_block_do_not_reinstate_the_removed_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            path.write_text(json.dumps({'date_utc': '2026-09-29',
                'requests_reserved': 40, 'successful_responses': 2,
                'observed_tokens': 14, 'blocked': True}))
            state = DailyRequestBudget(path, now=lambda: datetime(2026, 9, 29, tzinfo=timezone.utc))
            self.assertTrue(state.can_request)
            self.assertEqual(state.data['successful_responses'], 2)
            self.assertEqual(state.data['observed_tokens'], 14)
            self.assertNotIn('requests_reserved', state.data)

    def test_rate_limit_stops_run_and_persists_retry_after_across_midnight(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            clock = [datetime(2026, 9, 28, 23, 59, 30, tzinfo=timezone.utc)]
            state = DailyRequestBudget(path, now=lambda: clock[0])
            error = RuntimeError('private provider response')
            error.status_code = 429
            error.response = SimpleNamespace(headers={'Retry-After': '120'})
            state.record_failure(error)
            self.assertFalse(state.can_request)
            clock[0] = datetime(2026, 9, 29, 0, 0, 30, tzinfo=timezone.utc)
            resumed = DailyRequestBudget(path, now=lambda: clock[0])
            self.assertFalse(resumed.can_request)
            clock[0] = datetime(2026, 9, 29, 0, 1, 31, tzinfo=timezone.utc)
            self.assertTrue(resumed.can_request)
            self.assertFalse(state.can_request)
            self.assertNotIn('private provider', path.read_text())

    def test_unknown_limit_does_not_mean_exhausted_for_the_entire_day(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            for code in (402, 429):
                with self.subTest(code=code):
                    state = DailyRequestBudget(path)
                    error = RuntimeError('unavailable')
                    error.status_code = code
                    state.record_failure(error)
                    self.assertFalse(state.can_request)
                    self.assertTrue(DailyRequestBudget(path).can_request)

    def test_http_date_retry_after_and_invalid_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            clock = datetime(2026, 9, 29, tzinfo=timezone.utc)
            for header, expected in (('Tue, 29 Sep 2026 00:02:00 GMT', 1790640120.0),
                                     ('not-a-date', 0.0)):
                with self.subTest(header=header):
                    if path.exists():
                        path.unlink()
                    state = DailyRequestBudget(path, now=lambda: clock)
                    error = RuntimeError('unavailable')
                    error.status_code = 429
                    error.headers = {'retry-after': header}
                    state.record_failure(error)
                    self.assertEqual(state.data['cooldown_until_epoch'], expected)
                    self.assertFalse(state.can_request)

    def test_invalid_state_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            path.write_text('{broken')
            with self.assertRaises(ValueError):
                DailyRequestBudget(path)

    def test_openrouter_reset_blocks_later_runs_until_exact_provider_time(self):
        # Removing reset parsing would allow another run to call before midnight.
        for location in ('headers', 'sdk_message'):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'budget.json'
                clock = [datetime(2026, 10, 5, 14, 17, tzinfo=timezone.utc)]
                headers = {'X-RateLimit-Limit': '50', 'X-RateLimit-Remaining': '0',
                           'X-RateLimit-Reset': '1791244800000'}
                payload = {'error': {'code': 429, 'message': 'free-models-per-day',
                           'metadata': {'headers': headers,
                                        'limit_source': 'openrouter_free_tier_daily'}},
                           'user_id': 'private-fixture'}
                error = RuntimeError('litellm.RateLimitError: OpenrouterException - ' +
                                     json.dumps(payload) if location == 'sdk_message' else 'limit')
                error.status_code = 429
                error.response = SimpleNamespace(headers=headers if location == 'headers' else {})
                state = DailyRequestBudget(path, now=lambda: clock[0])
                state.record_failure(error)
                clock[0] = datetime(2026, 10, 5, 23, 59, 59, tzinfo=timezone.utc)
                resumed = DailyRequestBudget(path, now=lambda: clock[0])
                self.assertFalse(resumed.can_request)
                self.assertEqual(resumed.data['cooldown_until_epoch'], 1791244800.0)
                self.assertNotIn('private-fixture', path.read_text())
                clock[0] = datetime(2026, 10, 6, tzinfo=timezone.utc)
                self.assertTrue(resumed.can_request)

    def test_reset_does_not_shorten_retry_after(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'
            state = DailyRequestBudget(path, now=lambda: datetime(2026, 10, 5, 23, 59, tzinfo=timezone.utc))
            error = RuntimeError('limit')
            error.status_code = 429
            error.headers = {'Retry-After': '120', 'X-RateLimit-Reset': '1791244800000'}
            state.record_failure(error)
            self.assertEqual(state.data['cooldown_until_epoch'], 1791244860.0)

    def test_invalid_or_expired_reset_does_not_create_a_longer_pause(self):
        for reset in ('garbage', 'NaN', 'Infinity', '-1', '1791158400000'):
            with self.subTest(reset=reset), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'budget.json'
                state = DailyRequestBudget(path, now=lambda: datetime(2026, 10, 5, 14, tzinfo=timezone.utc))
                error = RuntimeError('limit')
                error.status_code = 429
                error.headers = {'X-RateLimit-Reset': reset}
                state.record_failure(error)
                self.assertFalse(state.can_request)
                self.assertTrue(DailyRequestBudget(path, now=state.now).can_request)


if __name__ == '__main__':
    unittest.main()
