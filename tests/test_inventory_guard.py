import asyncio
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from bot_runtime import run_forecasts
from runtime_policy import SkipRecord
from test_bot_runtime import Bot, Client, question


def row(qid, status='open'):
    return {'question_id': qid, 'post_id': qid + 100, 'source': 'minibench',
            'status': status, 'open_time_utc': '2026-09-28T14:00:00+00:00',
            'close_time_utc': '2026-09-28T17:00:00+00:00',
            'already_forecasted': False}


async def empty_inventory(target):
    return {'complete': True, 'questions': [], 'post_count': 0}


class InventoryGuardTests(unittest.TestCase):
    def test_silent_empty_sdk_result_is_detected_against_raw_inventory(self):
        async def inventory(target):
            return {'complete': True, 'questions': [row(7)] if target == 'minibench' else [], 'post_count': 1}
        _, result = asyncio.run(run_forecasts(Client(), Bot(), 'tournament', fetch_inventory=inventory))
        self.assertTrue(result['needs_attention'])
        self.assertEqual(result['status'], 'attention_required')
        self.assertEqual(result['pending_questions'][0]['question_id'], 7)
        self.assertEqual(result['pending_questions'][0]['reason'], 'retrieval_missing')

    def test_failed_audit_is_unknown_not_zero_but_does_not_block_valid_forecasts(self):
        async def inventory(target):
            raise TimeoutError('secret not for logging')
        _, result = asyncio.run(run_forecasts(Client([question(1)]), Bot(), 'tournament', fetch_inventory=inventory))
        self.assertEqual(result['submitted'], 1)
        self.assertTrue(result['needs_attention'])
        self.assertEqual(result['status'], 'attention_required')
        self.assertNotIn('secret', str(result))
        self.assertEqual(result['retrieval_audit'][0]['status'], 'failed')

    def test_one_target_failure_does_not_prevent_other_target_submission(self):
        async def fetch(target):
            if target == 'minibench':
                raise TimeoutError()
            return [question(8)]
        _, result = asyncio.run(run_forecasts(fetch, Bot(), 'tournament', fetch_inventory=empty_inventory))
        self.assertEqual(result['submitted'], 1)
        self.assertTrue(result['needs_attention'])
        self.assertIsNone(result['open_questions_returned'][0])

    def test_any_policy_skip_remains_an_incident_even_if_named_as_expected(self):
        with patch('bot_runtime.select_eligible_questions', return_value=([], [SkipRecord(1, 'minibench', 'invented_policy')])):
            _, result = asyncio.run(run_forecasts(Client([question(1)]), Bot(), 'tournament', fetch_inventory=empty_inventory))
        self.assertTrue(result['needs_attention'])
        self.assertEqual(result['status'], 'attention_required')
        self.assertEqual(result['pending_questions'][0]['reason'], 'invented_policy')

    def test_both_empty_and_successfully_audited_can_be_no_new_questions(self):
        _, result = asyncio.run(run_forecasts(Client(), Bot(), 'tournament', fetch_inventory=empty_inventory))
        self.assertFalse(result['needs_attention'])
        self.assertEqual(result['status'], 'no_new_questions')

    def test_audit_absent_is_not_healthy(self):
        _, result = asyncio.run(run_forecasts(Client(), Bot(), 'tournament'))
        self.assertTrue(result['needs_attention'])

    def test_sdk_already_answered_flag_cannot_hide_raw_unanswered_evidence(self):
        q = question(7)
        q.already_forecasted = True
        async def inventory(target):
            return {'complete': True, 'questions': [row(7)] if target == 'minibench' else [], 'post_count': 1}
        _, result = asyncio.run(run_forecasts(Client([q]), Bot(), 'tournament', fetch_inventory=inventory))
        self.assertTrue(result['needs_attention'])
        self.assertEqual(result['pending_questions'][0]['reason'], 'forecast_evidence_mismatch')

    def test_partial_success_is_not_a_green_completed_run(self):
        _, result = asyncio.run(run_forecasts(Client([question(n) for n in range(13)]), Bot(), 'tournament', fetch_inventory=empty_inventory))
        self.assertEqual(result['submitted'], 12)
        self.assertEqual(result['status'], 'attention_required')

    def test_unknown_raw_forecast_evidence_is_not_claimed_as_confirmed_unanswered(self):
        q = question(7)
        q.already_forecasted = True
        async def inventory(target):
            return {'complete': True, 'questions': [{**row(7), 'already_forecasted': None}] if target == 'minibench' else [], 'post_count': 1}
        _, result = asyncio.run(run_forecasts(Client([q]), Bot(), 'tournament', fetch_inventory=inventory))
        self.assertTrue(result['needs_attention'])
        self.assertEqual(result['pending_questions'][0]['reason'], 'forecast_evidence_unknown')

    def test_incomplete_inventory_cannot_assert_empty(self):
        async def inventory(target):
            return {'complete': False, 'questions': [], 'post_count': 1000}
        _, result = asyncio.run(run_forecasts(Client(), Bot(), 'tournament', fetch_inventory=inventory))
        self.assertTrue(result['needs_attention'])
        self.assertEqual(result['retrieval_audit'][0]['status'], 'failed')

    def test_closed_metadata_preserved_but_not_pending(self):
        async def inventory(target):
            return {'complete': True, 'questions': [row(7, 'closed')], 'post_count': 1}
        _, result = asyncio.run(run_forecasts(Client(), Bot(), 'tournament', fetch_inventory=inventory))
        self.assertEqual(result['pending_questions'], [])
        self.assertFalse(result['needs_attention'])
        self.assertEqual(result['retrieval_audit'][0]['questions'][0]['status'], 'closed')


if __name__ == '__main__':
    unittest.main()
