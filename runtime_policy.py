"""Small zero-new-cost run guards and tournament question selection."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Mapping, Sequence


FORECASTING_PRINCIPLES = (
    "Start with relevant base rates, then update from evidence and current verified facts; "
    "state what remains unknown. Examine stakeholder incentives, including emotion only "
    "when supported by observable evidence, never nationality or ethnicity stereotypes. "
    "Separate what should happen from what will happen. Test a credible counter-scenario "
    "and allow for unknown unknowns. If research is empty, never pretend to have done "
    "live research or verified current events."
)

_PLACEHOLDERS = frozenset(
    {
        "1234567890",
        "replace_me",
        "changeme",
        "placeholder",
        "none",
        "null",
        "your-token-here",
        "your-api-key-here",
        "your_metaculus_token",
        "your_openrouter_api_key",
    }
)
_ELECTION_TERMS = re.compile(
    r"\b(?:elections?|elect(?:ed|oral)|ballots?|referend(?:um|a)|"
    r"popular\s+vote|votes?|voter\s+turnout|voting\s+results|"
    r"presidenc(?:y|ies)|presidential|parliamentary|congressional|gubernatorial|senate\s+race|"
    r"mayoral\s+race|(?:senate|parliament|congress|house)\s+seats?|electoral\s+college)\b",
    re.IGNORECASE,
)
_BOARD_ELECTION = re.compile(
    r"\b(?:election\s+of\s+(?:the\s+)?board(?:\s+members)?|"
    r"board(?:\s+of\s+directors)?\s+election)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SkipRecord:
    question_id: Any
    source: str
    reason: str


def validate_zero_cost_environment(environ: Mapping[str, str] | None = None) -> None:
    """Fail closed unless both publishing and free-router credentials are real."""
    values = os.environ if environ is None else environ
    missing = [
        name
        for name in ("METACULUS_TOKEN", "OPENROUTER_API_KEY")
        if not (value := (values.get(name) or "").strip())
        or value.casefold() in _PLACEHOLDERS
    ]
    if missing:
        # Never include the values in logs or exception messages.
        raise RuntimeError("Missing or placeholder required environment variable(s): " + ", ".join(missing))


def require_zero_cost_mode(mode: str) -> None:
    """Disallow the unbounded/paid cup branch before constructing the bot."""
    if mode not in ("tournament", "test_questions"):
        raise ValueError("Only tournament and test_questions are allowed for zero-cost runs")


def _is_election_related(question: Any) -> bool:
    text = "\n".join(
        str(getattr(question, field, "") or "")
        for field in ("question_text", "background_info", "resolution_criteria", "fine_print")
    )
    # A corporate board election is not a public vote-outcome forecast.
    text = _BOARD_ELECTION.sub("", text)
    return bool(_ELECTION_TERMS.search(text))


def select_eligible_questions(
    minibench_questions: Sequence[Any],
    seasonal_questions: Sequence[Any],
    limit: int = 12,
) -> tuple[list[Any], list[SkipRecord]]:
    """Prioritize MiniBench, never exceed 12, and account for every omitted item."""
    if limit < 0:
        raise ValueError("limit must be nonnegative")
    budget = min(limit, 12)
    selected: list[Any] = []
    records: list[SkipRecord] = []
    seen_ids: set[Any] = set()
    forecasted_ids = {
        question.id_of_question
        for question in (*minibench_questions, *seasonal_questions)
        if question.already_forecasted
    }
    for source, questions in (("minibench", minibench_questions), ("seasonal", seasonal_questions)):
        for question in questions:
            question_id = question.id_of_question
            if question_id in seen_ids:
                reason = "duplicate"
            else:
                seen_ids.add(question_id)
                if question_id in forecasted_ids:
                    reason = "already_forecasted"
                elif _is_election_related(question):
                    reason = "election_policy"
                elif len(selected) >= budget:
                    reason = "batch_limit"
                else:
                    selected.append(question)
                    continue
            records.append(SkipRecord(question_id, source, reason))
    return selected, records
