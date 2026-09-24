"""Small, auditable runner around the official forecasting bot."""
from dataclasses import asdict
from datetime import datetime, timezone
from runtime_policy import require_zero_cost_mode, select_eligible_questions

MINIBENCH = 'minibench'
FUTUREEVAL = 'fall-futureeval-2026'


async def run_forecasts(fetch_questions, bot, mode, budget=None):
    require_zero_cost_mode(mode)
    result = {
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': mode,
        'targets': [MINIBENCH, FUTUREEVAL] if mode == 'tournament' else ['bot-testing-area'],
        'model_route': 'openrouter/openrouter/free',
        'actual_routed_models': None,
        'external_research': False,
        'credit_approval': 'unverified',
        'credit_balance': None,
        'api_call_count': None,
        'api_token_usage': None,
        'official_score': None,
        'official_rank': None,
        'prize_usd': None,
        'cost_measurement': 'Free-only route; estimated costs cover returned reports, not provider billing',
        'new_spending_usd': 0,
        'submitted': 0,
        'failed_or_unconfirmed': 0,
        'estimated_llm_cost_usd': 0.0,
        'outcomes': [],
        'skips': [],
        'status': 'started',
    }
    reports = []
    try:
        primary = await fetch_questions(result['targets'][0])
        seasonal = (await fetch_questions(FUTUREEVAL)
                    if mode == 'tournament' else [])
    except Exception as exc:
        result.update(status='fetch_failed', error_type=type(exc).__name__)
        return reports, result

    result['open_questions_returned'] = [len(primary), len(seasonal)]
    selected, skips = select_eligible_questions(primary, seasonal, limit=12 if mode == 'tournament' else 1)
    result['skips'] = [asdict(record) for record in skips]
    result['selected'] = len(selected)
    # Filtering above already excludes prior forecasts; no human selects a forecast.
    bot.skip_previously_forecasted_questions = False
    for question in selected:
        # Ordinary forecasts require generation plus parsing; never start a
        # fresh question when we cannot reserve those two attempts.
        if budget is not None and budget.remaining < 2:
            result['skips'].append({'question_id': question.id_of_question,
                                    'source': 'selected', 'reason': 'daily_request_budget'})
            continue
        try:
            report = await bot.forecast_question(question, return_exceptions=True)
        except Exception as exc:
            report = exc
        reports.append(report)
        outcome = {'question_id': question.id_of_question}
        if isinstance(report, BaseException):
            # A comment failure may follow a successful prediction POST.
            # Do not claim it was submitted or safe to blindly retry.
            result['failed_or_unconfirmed'] += 1
            outcome.update(status='failed_or_unconfirmed', error_type=type(report).__name__)
        else:
            result['submitted'] += 1
            outcome.update(status='submitted', nonfatal_errors=len(report.errors))
            result['estimated_llm_cost_usd'] += report.price_estimate or 0.0
        result['outcomes'].append(outcome)
    result['status'] = ('partial_failure' if result['submitted'] else 'failed') if result['failed_or_unconfirmed'] else ('completed' if reports else ('quota_exhausted' if selected else 'no_new_questions'))
    result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    return reports, result
