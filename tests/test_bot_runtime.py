import asyncio
import unittest
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
    def test_exhausted_budget_never_calls_forecaster(self):
        bot = Bot()
        reports, result = asyncio.run(run_forecasts(Client([question(12)]), bot,
            'tournament', budget=SimpleNamespace(remaining=0)))
        self.assertEqual(bot.calls, [])
        self.assertEqual(result['status'], 'quota_exhausted')
        self.assertEqual(result['skips'][0]['reason'], 'daily_request_budget')

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
        self.assertEqual(bot.calls, [])
        self.assertNotIn('secret', str(result))


if __name__ == '__main__':
    unittest.main()
