"""Exercise the locked SDK boundary in Actions; no provider request is sent."""
import asyncio
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


@unittest.skipUnless(importlib.util.find_spec('forecasting_tools'), 'SDK installed in Actions')
class SdkBudgetTests(unittest.TestCase):
    def check(self, scenario):
        from main import BudgetedFreeLlm
        from request_budget import DailyRequestBudget

        async def run(path):
            BudgetedFreeLlm.budget = DailyRequestBudget(path)
            BudgetedFreeLlm.last_request_at = 0.0
            BudgetedFreeLlm.request_lock = asyncio.Lock()
            with patch('main.asyncio.sleep', new_callable=AsyncMock):
                await scenario(BudgetedFreeLlm, path)
        with tempfile.TemporaryDirectory() as folder:
            asyncio.run(run(Path(folder) / 'budget.json'))

    def test_generation_and_parser_are_not_blocked_by_local_counts(self):
        from main import GeneralLlm

        async def scenario(llm, path):
            llm.budget.data['successful_responses'] = 50
            generator, parser = llm(temperature=0.3), llm(temperature=0)
            with patch.object(GeneralLlm, '_mockable_direct_call_to_model',
                              new_callable=AsyncMock,
                              return_value=SimpleNamespace(total_tokens_used=7)) as provider:
                await generator._mockable_direct_call_to_model('fixture')
                await parser._mockable_direct_call_to_model('fixture')
                self.assertEqual(provider.await_count, 2)
                self.assertEqual(llm.budget.session_responses, 2)
                self.assertEqual(llm.budget.session_tokens, 14)
                self.assertEqual(llm.budget.data['successful_responses'], 52)
        self.check(scenario)

    def test_presend_failure_does_not_consume_a_request_or_block_next_call(self):
        from main import GeneralLlm

        async def scenario(llm, path):
            model = llm(temperature=0)
            with patch.object(GeneralLlm, '_mockable_direct_call_to_model',
                              new_callable=AsyncMock,
                              side_effect=[ValueError('local validation'),
                                           SimpleNamespace(total_tokens_used=7)]) as provider:
                with self.assertRaises(ValueError):
                    await model._mockable_direct_call_to_model('fixture')
                self.assertEqual(llm.budget.session_responses, 0)
                self.assertEqual(llm.budget.session_tokens, 0)
                self.assertNotIn('requests_reserved', llm.budget.data)
                self.assertTrue(llm.budget.can_request)
                await model._mockable_direct_call_to_model('fixture')
                self.assertEqual(llm.budget.session_responses, 1)
                self.assertEqual(llm.budget.session_failures, 1)
                self.assertEqual(provider.await_count, 2)
        self.check(scenario)

    def test_transient_generation_failure_gets_one_bounded_retry(self):
        from main import GeneralLlm

        async def scenario(llm, path):
            model = llm(temperature=0.3)
            with patch.object(
                GeneralLlm,
                '_mockable_direct_call_to_model',
                new_callable=AsyncMock,
                side_effect=[
                    TimeoutError('transient free-provider timeout'),
                    SimpleNamespace(total_tokens_used=7, data='recovered'),
                ],
            ) as provider:
                result = await model.invoke('fixture')

            self.assertEqual(result, 'recovered')
            self.assertEqual(provider.await_count, 2)
            self.assertEqual(llm.budget.session_failures, 1)
            self.assertEqual(llm.budget.session_responses, 1)

        self.check(scenario)

    def test_provider_limit_prevents_further_generation_or_parsing_in_run(self):
        from main import GeneralLlm
        from request_budget import ProviderPaused

        async def scenario(llm, path):
            error = RuntimeError('provider response must not be persisted')
            error.status_code = 429
            error.response = SimpleNamespace(headers={'Retry-After': '120'})
            with patch.object(GeneralLlm, '_mockable_direct_call_to_model',
                              new_callable=AsyncMock, side_effect=error) as provider:
                with self.assertRaises(RuntimeError):
                    await llm(temperature=0.3)._mockable_direct_call_to_model('fixture')
                with self.assertRaises(ProviderPaused):
                    await llm(temperature=0)._mockable_direct_call_to_model('fixture')
                self.assertEqual(provider.await_count, 1)
                self.assertEqual(llm.budget.session_responses, 0)
                self.assertEqual(llm.budget.session_failures, 1)
                self.assertNotIn('provider response', path.read_text())
        self.check(scenario)

    def test_bounded_retry_does_not_repeat_a_provider_limit_request(self):
        from main import GeneralLlm
        from request_budget import ProviderPaused

        async def scenario(llm, path):
            error = RuntimeError('provider rate limit')
            error.status_code = 429
            error.response = SimpleNamespace(headers={'Retry-After': '120'})
            model = llm(temperature=0.3)
            with patch.object(
                GeneralLlm,
                '_mockable_direct_call_to_model',
                new_callable=AsyncMock,
                side_effect=error,
            ) as provider:
                with self.assertRaises(ProviderPaused):
                    await model.invoke('fixture')

            self.assertEqual(provider.await_count, 1)
            self.assertEqual(llm.budget.session_failures, 1)
            self.assertEqual(llm.budget.session_responses, 0)

        self.check(scenario)

    def test_wait_failure_before_provider_entry_has_no_request_count(self):
        from main import GeneralLlm

        async def scenario(llm, path):
            import time
            llm.last_request_at = time.monotonic()
            with patch('main.asyncio.sleep', new_callable=AsyncMock,
                       side_effect=ValueError('before provider')):
                with patch.object(GeneralLlm, '_mockable_direct_call_to_model',
                                  new_callable=AsyncMock) as provider:
                    with self.assertRaises(ValueError):
                        await llm(temperature=0)._mockable_direct_call_to_model('fixture')
                    self.assertEqual(provider.await_count, 0)
                    self.assertEqual(llm.budget.session_responses, 0)
                    self.assertEqual(llm.budget.session_failures, 0)
        self.check(scenario)

    def test_multiple_choice_parser_retries_one_malformed_free_response(self):
        from main import PredictedOptionList, SummerTemplateBot2026

        async def scenario():
            bot = object.__new__(SummerTemplateBot2026)
            bot._structure_output_validation_samples = 1
            model = SimpleNamespace(
                invoke=AsyncMock(return_value='Analysis without an exact final line')
            )
            bot.get_llm = lambda *args: model
            question = SimpleNamespace(options=['Option A'], page_url='fixture')
            parsed = PredictedOptionList(
                predicted_options=[{'option_name': 'Option A', 'probability': 1.0}]
            )
            with patch('main.structure_output', new_callable=AsyncMock,
                       return_value=parsed) as parser:
                await bot._multiple_choice_prompt_to_forecast(question, 'fixture')
                self.assertEqual(parser.await_args.kwargs['allowed_tries'], 2)

        asyncio.run(scenario())

    def test_multiple_choice_uses_exact_probability_lines_before_model_conversion(self):
        from main import SummerTemplateBot2026

        async def scenario():
            bot = object.__new__(SummerTemplateBot2026)
            bot._structure_output_validation_samples = 1
            reasoning = "Analysis omitted.\n\nYes: 60%\nNo: 40%\n"
            model = SimpleNamespace(invoke=AsyncMock(return_value=reasoning))
            bot.get_llm = lambda *args: model
            question = SimpleNamespace(options=['Yes', 'No'], page_url='fixture')
            with patch(
                'main.structure_output',
                new_callable=AsyncMock,
                side_effect=ValueError('model conversion should not be called'),
            ) as parser:
                result = await bot._multiple_choice_prompt_to_forecast(
                    question, 'fixture'
                )

            self.assertEqual(parser.await_count, 0)
            self.assertEqual(
                [item.option_name for item in result.prediction_value.predicted_options],
                ['Yes', 'No'],
            )
            self.assertEqual(
                [item.probability for item in result.prediction_value.predicted_options],
                [0.6, 0.4],
            )

        asyncio.run(scenario())

    def test_binary_parser_uses_exact_probability_line_before_model_conversion(self):
        from main import SummerTemplateBot2026

        async def scenario():
            bot = object.__new__(SummerTemplateBot2026)
            bot._structure_output_validation_samples = 1
            reasoning = "Analysis omitted.\n\nProbability: 60%\n"
            model = SimpleNamespace(invoke=AsyncMock(return_value=reasoning))
            bot.get_llm = lambda *args: model
            question = SimpleNamespace(page_url='fixture')
            with patch(
                'main.structure_output',
                new_callable=AsyncMock,
                side_effect=ValueError('model conversion should not be called'),
            ) as parser:
                result = await bot._binary_prompt_to_forecast(question, 'fixture')

            self.assertEqual(parser.await_count, 0)
            self.assertEqual(result.prediction_value, 0.6)

        asyncio.run(scenario())

    def test_binary_parser_accepts_markdown_bold_probability_line(self):
        from main import SummerTemplateBot2026

        async def scenario():
            bot = object.__new__(SummerTemplateBot2026)
            bot._structure_output_validation_samples = 1
            reasoning = "Analysis omitted.\n\n**Probability: 60%**\n"
            model = SimpleNamespace(invoke=AsyncMock(return_value=reasoning))
            bot.get_llm = lambda *args: model
            question = SimpleNamespace(page_url='fixture')
            with patch(
                'main.structure_output',
                new_callable=AsyncMock,
                side_effect=ValueError('free parser returned no JSON'),
            ) as parser:
                result = await bot._binary_prompt_to_forecast(question, 'fixture')

            self.assertEqual(model.invoke.await_count, 1)
            self.assertEqual(parser.await_count, 0)
            self.assertEqual(result.prediction_value, 0.6)

        asyncio.run(scenario())

    def test_binary_forecast_retries_one_successful_but_unusable_generation(self):
        from main import SummerTemplateBot2026

        async def scenario():
            bot = object.__new__(SummerTemplateBot2026)
            bot._structure_output_validation_samples = 1
            model = SimpleNamespace(
                invoke=AsyncMock(side_effect=[
                    'User Safety: safe',
                    'Analysis omitted.\n\nProbability: 60%\n',
                ])
            )
            bot.get_llm = lambda *args: model
            question = SimpleNamespace(page_url='fixture')
            with patch(
                'main.structure_output',
                new_callable=AsyncMock,
                side_effect=ValueError('free parser returned no JSON'),
            ) as parser:
                result = await bot._binary_prompt_to_forecast(question, 'fixture')

            self.assertEqual(model.invoke.await_count, 2)
            self.assertEqual(parser.await_count, 1)
            self.assertEqual(result.prediction_value, 0.6)

        asyncio.run(scenario())

    def test_numeric_parser_recovers_after_two_malformed_free_responses(self):
        from main import NumericDistribution, SummerTemplateBot2026

        async def scenario():
            bot = object.__new__(SummerTemplateBot2026)
            bot._structure_output_validation_samples = 1
            model = SimpleNamespace(invoke=AsyncMock(return_value='Percentile 50: 10'))
            bot.get_llm = lambda *args: model
            question = SimpleNamespace(
                question_text='fixture',
                unit_of_measure='units',
                lower_bound=0,
                upper_bound=100,
                page_url='fixture',
            )
            prediction = SimpleNamespace(declared_percentiles=[])
            with patch('main.structure_output', new_callable=AsyncMock,
                       side_effect=[
                           ValueError('first malformed response'),
                           ValueError('second malformed response'),
                           [],
                       ]) as parser:
                with patch.object(NumericDistribution, 'from_question',
                                  return_value=prediction):
                    await bot._numeric_prompt_to_forecast(question, 'fixture')
                self.assertEqual(parser.await_count, 3)
                self.assertTrue(all(
                    call.kwargs['allowed_tries'] == 1
                    for call in parser.await_args_list
                ))

        asyncio.run(scenario())

    def test_numeric_parser_retries_percentiles_rejected_by_distribution_validation(self):
        from main import NumericDistribution, SummerTemplateBot2026

        async def scenario():
            bot = object.__new__(SummerTemplateBot2026)
            bot._structure_output_validation_samples = 1
            model = SimpleNamespace(invoke=AsyncMock(return_value='Percentile 50: 10'))
            bot.get_llm = lambda *args: model
            question = SimpleNamespace(
                question_text='fixture',
                unit_of_measure='units',
                lower_bound=0,
                upper_bound=100,
                page_url='fixture',
            )
            invalid_percentiles = [SimpleNamespace(value=20), SimpleNamespace(value=10)]
            valid_percentiles = [SimpleNamespace(value=10), SimpleNamespace(value=20)]
            prediction = SimpleNamespace(declared_percentiles=valid_percentiles)
            with patch(
                'main.structure_output',
                new_callable=AsyncMock,
                side_effect=[invalid_percentiles, valid_percentiles],
            ) as parser:
                with patch.object(
                    NumericDistribution,
                    'from_question',
                    side_effect=[ValueError('Percentiles must be in strictly increasing order'), prediction],
                ):
                    result = await bot._numeric_prompt_to_forecast(question, 'fixture')
                self.assertIs(result.prediction_value, prediction)
                self.assertEqual(parser.await_count, 2)

        asyncio.run(scenario())

    def test_numeric_parser_falls_back_to_exact_percentile_lines(self):
        from main import SummerTemplateBot2026

        async def scenario():
            bot = object.__new__(SummerTemplateBot2026)
            bot._structure_output_validation_samples = 1
            reasoning = """
            Analysis omitted.
            Percentile 10: $1,000
            Percentile 20: $2,000
            Percentile 40: $4,000
            Percentile 60: $6,000
            Percentile 80: $8,000
            Percentile 90: $9,000
            """
            model = SimpleNamespace(invoke=AsyncMock(return_value=reasoning))
            bot.get_llm = lambda *args: model
            question = SimpleNamespace(
                question_text='fixture',
                unit_of_measure='$',
                lower_bound=0,
                upper_bound=10000,
                open_lower_bound=False,
                open_upper_bound=False,
                zero_point=None,
                cdf_size=201,
                page_url='fixture',
            )
            with patch(
                'main.structure_output',
                new_callable=AsyncMock,
                side_effect=ValueError('free parser returned no JSON'),
            ) as parser:
                result = await bot._numeric_prompt_to_forecast(question, 'fixture')

            self.assertEqual(parser.await_count, 3)
            self.assertEqual(
                [item.value for item in result.prediction_value.declared_percentiles],
                [1000, 2000, 4000, 6000, 8000, 9000],
            )

        asyncio.run(scenario())
