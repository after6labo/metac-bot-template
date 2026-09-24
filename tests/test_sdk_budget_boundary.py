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
    def test_generation_and_parser_share_quota_before_provider_call(self):
        from main import BudgetedFreeLlm, GeneralLlm
        from request_budget import DailyRequestBudget, BudgetExhausted

        async def check(path):
            BudgetedFreeLlm.budget = DailyRequestBudget(path, limit=1)
            BudgetedFreeLlm.last_request_at = 0.0
            BudgetedFreeLlm.request_lock = asyncio.Lock()
            generator = BudgetedFreeLlm(temperature=0.3)
            parser = BudgetedFreeLlm(temperature=0)
            with patch.object(GeneralLlm, '_mockable_direct_call_to_model',
                              new_callable=AsyncMock,
                              return_value=SimpleNamespace(total_tokens_used=7)) as provider:
                await generator._mockable_direct_call_to_model('fixture')
                with self.assertRaises(BudgetExhausted):
                    await parser._mockable_direct_call_to_model('fixture')
                self.assertEqual(provider.await_count, 1)
                self.assertEqual(BudgetedFreeLlm.budget.data['observed_tokens'], 7)

        with tempfile.TemporaryDirectory() as folder:
            asyncio.run(check(Path(folder) / 'budget.json'))
