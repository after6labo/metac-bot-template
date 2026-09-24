"""Behavioral guardrails for zero-new-cost tournament selection."""

import unittest
from types import SimpleNamespace

from runtime_policy import (
    FORECASTING_PRINCIPLES,
    require_zero_cost_mode,
    select_eligible_questions,
    validate_zero_cost_environment,
)


def question(question_id, text, **fields):
    return SimpleNamespace(
        id_of_question=question_id,
        question_text=text,
        background_info=fields.get("background_info", ""),
        resolution_criteria=fields.get("resolution_criteria", ""),
        fine_print=fields.get("fine_print", ""),
        already_forecasted=fields.get("already_forecasted", False),
    )


class ZeroCostEnvironmentTests(unittest.TestCase):
    def test_requires_both_specific_real_credentials_without_exposing_values(self):
        secret = "sensitive-token-should-not-appear"
        for credentials in (
            {},
            {"METACULUS_TOKEN": secret},
            {"METACULUS_TOKEN": secret, "OPENROUTER_API_KEY": "  "},
            {"METACULUS_TOKEN": "replace_me", "OPENROUTER_API_KEY": secret},
            {"METACULUS_TOKEN": secret, "OPENROUTER_API_KEY": "your-api-key-here"},
        ):
            with self.subTest(credentials=tuple(credentials)):
                with self.assertRaises(RuntimeError) as caught:
                    validate_zero_cost_environment(credentials)
                self.assertNotIn(secret, str(caught.exception))
        validate_zero_cost_environment(
            {"METACULUS_TOKEN": "  real-metaculus  ", "OPENROUTER_API_KEY": "real-router"}
        )

    def test_other_llm_key_does_not_replace_openrouter_key(self):
        with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
            validate_zero_cost_environment(
                {"METACULUS_TOKEN": "valid", "OPENAI_API_KEY": "valid"}
            )

    def test_cup_mode_cannot_use_paid_fallback(self):
        with self.assertRaises(ValueError):
            require_zero_cost_mode("metaculus_cup")
        for mode in ("tournament", "test_questions"):
            require_zero_cost_mode(mode)


class SelectionTests(unittest.TestCase):
    def test_elected_and_seat_winner_wording_is_excluded(self):
        selected, records = select_eligible_questions([
            question(1, 'Will Alice be elected president of the United States in 2028?'),
            question(2, 'Who wins the US Senate seat in Ohio?'),
            question(3, 'Will Bob be elected governor of California?'),
        ], [])
        self.assertEqual(selected, [])
        self.assertEqual([r.reason for r in records], ['election_policy'] * 3)

    def test_minibench_first_skips_forecasted_and_deduplicates_by_id(self):
        first = question(11, "How many satellites?")
        already = question(12, "How many launches?", already_forecasted=True)
        duplicate = question(11, "Same forecast on a later tournament")
        seasonal = question(13, "Will the rover land?")
        selected, records = select_eligible_questions([first, already], [duplicate, seasonal])
        self.assertEqual([q.id_of_question for q in selected], [11, 13])
        self.assertEqual(
            [(record.question_id, record.source, record.reason) for record in records],
            [(12, "minibench", "already_forecasted"), (11, "seasonal", "duplicate")],
        )

    def test_same_id_marked_forecasted_anywhere_is_not_selected(self):
        selected, records = select_eligible_questions(
            [question(99, "Will the satellite launch?")],
            [question(99, "Will the satellite launch?", already_forecasted=True)],
        )
        self.assertEqual(selected, [])
        self.assertEqual([(r.question_id, r.reason) for r in records],
                         [(99, "already_forecasted"), (99, "duplicate")])

    def test_never_forecasts_more_than_twelve_and_records_deferred(self):
        selected, records = select_eligible_questions(
            [question(i, f"Question {i}") for i in range(10)],
            [question(i, f"Question {i}") for i in range(10, 15)],
        )
        self.assertEqual([q.id_of_question for q in selected], list(range(12)))
        self.assertEqual(
            [(r.question_id, r.reason) for r in records],
            [(12, "batch_limit"), (13, "batch_limit"), (14, "batch_limit")],
        )

    def test_requested_limit_cannot_raise_fixed_twelve_question_cap(self):
        selected, records = select_eligible_questions(
            [question(i, f"Question {i}") for i in range(14)], [], limit=100
        )
        self.assertEqual(len(selected), 12)
        self.assertEqual([(r.question_id, r.reason) for r in records],
                         [(12, "batch_limit"), (13, "batch_limit")])

    def test_implicit_electoral_vote_or_presidency_outcomes_are_excluded(self):
        selected, records = select_eligible_questions(
            [question(1, "Who will win the presidency?"),
             question(2, "What will the vote count be?"),
             question(3, "Will candidate A receive more votes than candidate B?")], []
        )
        self.assertEqual(selected, [])
        self.assertEqual([(r.question_id, r.reason) for r in records],
                         [(1, "election_policy"), (2, "election_policy"), (3, "election_policy")])

    def test_election_in_every_question_field_is_excluded(self):
        election_terms = (
            ("question_text", "Will the presidential election have a winner?"),
            ("background_info", "Election polling favors the incumbent."),
            ("resolution_criteria", "Resolves by the popular vote share."),
            ("fine_print", "Results after the referendum are final."),
        )
        for field, value in election_terms:
            with self.subTest(field=field):
                kwargs = {field: value}
                text = kwargs.pop("question_text", "Will this resolve by December?")
                selected, records = select_eligible_questions([question(1, text, **kwargs)], [])
                self.assertEqual(selected, [])
                self.assertEqual([(r.question_id, r.reason) for r in records], [(1, "election_policy")])

    def test_harmless_word_fragments_and_board_selection_are_eligible(self):
        selected, records = select_eligible_questions(
            [question(1, "Will electronic voting equipment ship?"),
             question(2, "Will the election of board members finish?"),
             question(3, "Will a candidate vaccine pass trials?")],
            [],
        )
        self.assertEqual([q.id_of_question for q in selected], [1, 2, 3])
        self.assertEqual(records, [])

    def test_prompt_guidance_has_honest_uncertainty_and_stakeholder_constraints(self):
        guidance = FORECASTING_PRINCIPLES.lower()
        for concept in ("base rate", "verified", "unknown", "incentive", "emotion", "observable", "stereotype", "should", "will", "counter", "live research"):
            with self.subTest(concept=concept):
                self.assertIn(concept, guidance)


if __name__ == "__main__":
    unittest.main()
