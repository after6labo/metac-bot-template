import io
import sys
import unittest
from contextlib import redirect_stdout
from types import ModuleType

import bot_helpers
from bot_helpers import print_run_summary_banner


class RunSummaryBannerTests(unittest.TestCase):
    def test_audit_only_attention_is_persisted_without_failing_the_action(self):
        result = {
            "needs_attention": True,
            "status": "attention_required",
            "pending_questions": [],
            "fetch_errors": [],
            "failed_or_unconfirmed": 0,
        }
        should_fail = getattr(bot_helpers, "should_fail_run", lambda _: True)
        self.assertFalse(should_fail(result))

    def test_unanswered_question_still_fails_the_action(self):
        result = {
            "needs_attention": True,
            "status": "attention_required",
            "pending_questions": [{"question_id": 1}],
            "fetch_errors": [],
            "failed_or_unconfirmed": 0,
        }
        should_fail = getattr(bot_helpers, "should_fail_run", lambda _: True)
        self.assertTrue(should_fail(result))

    def test_provider_paused_pending_questions_are_not_reported_as_no_new_questions(self):
        fake_module = ModuleType("forecasting_tools")
        fake_module.ForecastReport = type("ForecastReport", (), {})
        previous = sys.modules.get("forecasting_tools")
        sys.modules["forecasting_tools"] = fake_module
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                print_run_summary_banner(
                    [],
                    will_publish=True,
                    pending_questions=[{"question_id": 1}, {"question_id": 2}],
                    provider_paused=True,
                )
        finally:
            if previous is None:
                sys.modules.pop("forecasting_tools", None)
            else:
                sys.modules["forecasting_tools"] = previous

        self.assertIn("2 question(s) remain unanswered", output.getvalue())
        self.assertIn("provider paused", output.getvalue())
        self.assertNotIn("No new questions", output.getvalue())


if __name__ == "__main__":
    unittest.main()
