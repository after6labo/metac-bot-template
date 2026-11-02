"""Bounded numeric generation behavior; never calls a live provider.

Use the SDK class in CI. Without the optional SDK, compile the unchanged real
method in isolation; only its external conversion/distribution boundaries are
substituted. This does not claim SDK integration coverage locally.
"""
import ast
import asyncio
import importlib.util
import logging
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from request_budget import ProviderPaused


def numeric_boundary():
    if importlib.util.find_spec('forecasting_tools'):
        import main
        return main, main.SummerTemplateBot2026._numeric_prompt_to_forecast
    source = Path(__file__).resolve().parents[1] / 'main.py'
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'SummerTemplateBot2026')
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef)
                  and n.name == '_numeric_prompt_to_forecast')
    module = ast.Module(body=[ast.ImportFrom(module='__future__',
                       names=[ast.alias(name='annotations')], level=0), method],
                       type_ignores=[])
    scope = dict(ProviderPaused=ProviderPaused,
                 logger=logging.getLogger('numeric_boundary'),
                 clean_indents=dedent, structure_output=None,
                 NumericDistribution=SimpleNamespace(from_question=None),
                 Percentile=object, ReasonedPrediction=SimpleNamespace,
                 _parse_exact_numeric_percentile_lines=Mock(
                     side_effect=ValueError('no exact fixture lines')))
    exec(compile(ast.fix_missing_locations(module), str(source), 'exec'), scope)
    return SimpleNamespace(**scope), scope['_numeric_prompt_to_forecast']


class NumericGenerationRetryTests(unittest.TestCase):
    def exercise(self, generation, parsing=None):
        boundary, method = numeric_boundary()
        model = SimpleNamespace(invoke=AsyncMock(side_effect=generation))
        bot = SimpleNamespace(get_llm=lambda *args: model,
                              _structure_output_validation_samples=1)
        question = SimpleNamespace(page_url='fixture', question_text='fixture',
                                   unit_of_measure='units', lower_bound=0,
                                   upper_bound=100)
        prediction = SimpleNamespace(declared_percentiles=[])
        parser = AsyncMock(return_value=[], side_effect=parsing)
        # AST functions use the scope dict; SDK functions use main.__dict__.
        namespace = method.__globals__
        with patch.dict(namespace, structure_output=parser):
            with patch.object(boundary.NumericDistribution, 'from_question',
                              return_value=prediction):
                try:
                    result = asyncio.run(method(bot, question, 'unchanged fixture'))
                    error = None
                except BaseException as exc:
                    result, error = None, exc
        return result, error, model.invoke, parser, prediction

    def test_transient_generation_failures_recover_without_changing_reasoning(self):
        result, error, invoke, parser, prediction = self.exercise([
            AssertionError('empty response'), TimeoutError('timeout'), 'fixture reasoning'])
        self.assertIsNone(error)
        self.assertIs(result.prediction_value, prediction)
        self.assertEqual(result.reasoning, 'fixture reasoning')
        self.assertEqual(invoke.await_count, 3)
        self.assertTrue(all(c.args == ('unchanged fixture',) for c in invoke.await_args_list))
        self.assertEqual(parser.await_count, 1)

    def test_generation_exhaustion_stops_before_parsing(self):
        failure = AssertionError('empty response')
        result, error, invoke, parser, _ = self.exercise([failure] * 4)
        self.assertIs(error, failure)
        self.assertIsNone(result)
        self.assertEqual(invoke.await_count, 3)
        self.assertEqual(parser.await_count, 0)

    def test_provider_pause_is_never_retried(self):
        for failures in ([ProviderPaused('cooldown')],
                         [AssertionError('empty'), ProviderPaused('cooldown')]):
            with self.subTest(attempt=len(failures)):
                _, error, invoke, parser, _ = self.exercise(failures + ['must not run'])
                self.assertIs(error, failures[-1])
                self.assertEqual(invoke.await_count, len(failures))
                self.assertEqual(parser.await_count, 0)

    def test_conversion_failure_never_regenerates_successful_reasoning(self):
        failure = ValueError('unparseable fixture')
        _, error, invoke, parser, _ = self.exercise(['fixture reasoning'], [failure] * 3)
        self.assertIs(error, failure)
        self.assertEqual(invoke.await_count, 1)
        self.assertEqual(parser.await_count, 3)

    def test_cancellation_is_not_retried(self):
        failure = asyncio.CancelledError()
        _, error, invoke, parser, _ = self.exercise([failure])
        self.assertIs(error, failure)
        self.assertEqual(invoke.await_count, 1)
        self.assertEqual(parser.await_count, 0)

    def test_retry_diagnostics_do_not_include_error_body(self):
        with self.assertLogs(level='WARNING') as logs:
            _, error, _, _, _ = self.exercise([
                RuntimeError('PRIVATE_PROVIDER_BODY'), 'fixture reasoning'])
        self.assertIsNone(error)
        self.assertNotIn('PRIVATE_PROVIDER_BODY', '\n'.join(logs.output))
        self.assertIn('RuntimeError', '\n'.join(logs.output))
