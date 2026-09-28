import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bot_runtime import run_forecasts


def question(qid):
    return SimpleNamespace(id_of_question=qid, already_forecasted=False,
        question_text='Will the observatory open?', background_info='',
        resolution_criteria='', fine_print='')


class Client:
    def __init__(self, questions=None, error=False):
        self.questions = questions or []
        self.targets = []
        self.error = error

    async def __call__(self, target):
        self.targets.append(target)
        if self.error:
            raise RuntimeError('secret must not be recorded')
        return self.questions if target == 'minibench' else []


class Bot:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def forecast_question(self, q, return_exceptions=True):
        self.calls.append(q.id_of_question)
        if self.fail:
            return RuntimeError('secret must not be recorded')
        return SimpleNamespace(question=q, errors=[], price_estimate=0.0)


class RuntimeTests(unittest.TestCase):
    def test_failed_open_question_keeps_deadline_and_needs_attention(self):
        q = question(12)
        q.id_of_post = 10
        jst = timezone(timedelta(hours=9))
        q.open_time = datetime(2026, 9, 28, 23, tzinfo=jst)
        q.close_time = datetime(2026, 9, 29, 2, tzinfo=jst)
        q.api_json = {'credential': 'never include raw question data'}
        _, result = asyncio.run(run_forecasts(Client([q]), Bot(True), 'tournament'))
        self.assertTrue(result.get('needs_attention', False))
        pending = result['pending_questions']
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['question_id'], 12)
        self.assertEqual(pending[0]['post_id'], 10)
        self.assertEqual(pending[0]['open_time_utc'], '2026-09-28T14:00:00+00:00')
        self.assertEqual(pending[0]['close_time_utc'], '2026-09-28T17:00:00+00:00')
        self.assertEqual(pending[0]['reason'], 'failed_or_unconfirmed')
        self.assertNotIn('credential', str(result))

    def test_batch_deferred_question_is_not_hidden_by_other_submissions(self):
        _, result = asyncio.run(run_forecasts(Client([question(n) for n in range(13)]), Bot(), 'tournament'))
        self.assertEqual(result['submitted'], 12)
        self.assertTrue(result.get('needs_attention', False))
        self.assertEqual([q['question_id'] for q in result['pending_questions']], [12])
        self.assertEqual(result['pending_questions'][0]['reason'], 'batch_limit')

    def test_provider_pause_after_success_still_needs_attention(self):
        budget = SimpleNamespace(can_request=True)
        class PausingBot(Bot):
            async def forecast_question(self, q, return_exceptions=True):
                report = await super().forecast_question(q, return_exceptions)
                budget.can_request = False
                return report
        _, result = asyncio.run(run_forecasts(Client([question(1), question(2)]), PausingBot(), 'tournament', budget))
        self.assertEqual(result['submitted'], 1)
        self.assertTrue(result.get('needs_attention', False))
        self.assertEqual([q['question_id'] for q in result['pending_questions']], [2])
        self.assertEqual(result['pending_questions'][0]['reason'], 'provider_paused')

    def test_already_answered_and_duplicate_do_not_raise_false_alert(self):
        q = question(1)
        q.already_forecasted = True
        _, result = asyncio.run(run_forecasts(Client([q, q, question(2)]), Bot(), 'tournament'))
        self.assertEqual(result['submitted'], 1)
        self.assertIn('needs_attention', result)
        self.assertFalse(result['needs_attention'])
        self.assertEqual(result['pending_questions'], [])

    def test_provider_pause_never_calls_forecaster(self):
        bot = Bot()
        reports, result = asyncio.run(run_forecasts(Client([question(12)]), bot,
            'tournament', budget=SimpleNamespace(can_request=False)))
        self.assertEqual(bot.calls, [])
        self.assertEqual(result['status'], 'provider_paused')
        self.assertEqual(result['skips'][0]['reason'], 'provider_paused')

    def test_completed_responses_do_not_limit_new_questions(self):
        bot = Bot()
        reports, result = asyncio.run(run_forecasts(Client([question(12)]), bot,
            'tournament', budget=SimpleNamespace(can_request=True)))
        self.assertEqual(result['submitted'], 1)
        self.assertEqual(bot.calls, [12])

    def test_empty_targets_do_not_call_forecaster_and_use_fall(self):
        client, bot = Client(), Bot()
        reports, result = asyncio.run(run_forecasts(client, bot, 'tournament'))
        self.assertEqual(client.targets, ['minibench', 'fall-futureeval-2026'])
        self.assertEqual(bot.calls, [])
        self.assertEqual(reports, [])
        self.assertEqual(result['status'], 'no_new_questions')
        self.assertEqual(result['submitted'], 0)

    def test_publication_failure_is_not_counted_as_success_or_leaked(self):
        reports, result = asyncio.run(run_forecasts(Client([question(11)]), Bot(True), 'tournament'))
        self.assertEqual(result['submitted'], 0)
        self.assertEqual(result['failed_or_unconfirmed'], 1)
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('secret', str(result))

    def test_completed_report_counts_as_submission(self):
        reports, result = asyncio.run(run_forecasts(Client([question(12)]), Bot(), 'tournament'))
        self.assertEqual(result['submitted'], 1)
        self.assertEqual(result['failed_or_unconfirmed'], 0)
        self.assertEqual(result['outcomes'][0]['question_id'], 12)
        self.assertEqual(result['estimated_llm_cost_usd'], 0.0)

    def test_fetch_failure_has_failed_status_and_no_llm_calls(self):
        bot = Bot()
        reports, result = asyncio.run(run_forecasts(Client(error=True), bot, 'tournament'))
        self.assertEqual(result['status'], 'fetch_failed')
        self.assertTrue(result['needs_attention'])
        self.assertEqual(bot.calls, [])
        self.assertNotIn('secret', str(result))


if __name__ == '__main__':
    unittest.main()
