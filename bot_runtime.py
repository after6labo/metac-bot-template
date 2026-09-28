"""Small, auditable runner around the official forecasting bot."""
from dataclasses import asdict
from datetime import datetime, timezone
from runtime_policy import require_zero_cost_mode, select_eligible_questions

MINIBENCH = 'minibench'
FUTUREEVAL = 'fall-futureeval-2026'


def question_window(question, source):
    def utc_time(name):
        value = getattr(question, name, None)
        return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else None

    return {
        'question_id': question.id_of_question,
        'post_id': getattr(question, 'id_of_post', None),
        'source': source,
        'open_time_utc': utc_time('open_time'),
        'close_time_utc': utc_time('close_time'),
        'already_forecasted': bool(question.already_forecasted),
    }


async def run_forecasts(fetch_questions, bot, mode, budget=None, *, fetch_inventory=None):
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
        'question_windows': [],
        'pending_questions': [],
        'needs_attention': False,
        'fetch_errors': [],
        'retrieval_audit': [],
        'status': 'started',
    }
    reports = []
    fetched = []
    counts = []
    for target in result['targets']:
        try:
            questions = await fetch_questions(target)
            counts.append(len(questions))
            fetched.append(questions)
        except Exception as exc:
            result['fetch_errors'].append({'source': target, 'error_type': type(exc).__name__})
            counts.append(None)  # A failed read is not an empty list.
            fetched.append([])
    primary = fetched[0]
    seasonal = fetched[1] if mode == 'tournament' else []
    result['open_questions_returned'] = counts if mode == 'tournament' else counts + [0]

    # This read deliberately does not use the SDK's parsing or filtering path.
    # Audit errors must not suppress valid forecasts from the working path.
    inventory_open = []
    for target, questions in zip(result['targets'], fetched):
        if mode != 'tournament' and fetch_inventory is None:
            continue
        audit = {'source': target, 'checked_at_utc': datetime.now(timezone.utc).isoformat()}
        try:
            if fetch_inventory is None:
                raise RuntimeError('Inventory reader not configured')
            data = await fetch_inventory(target)
            if data.get('complete') is not True or not isinstance(data.get('questions'), list):
                raise ValueError('Incomplete inventory')
            raw_open = [row for row in data['questions'] if row['status'] == 'open']
            sdk_ids = {question.id_of_question for question in questions}
            missing = [row['question_id'] for row in raw_open if row['question_id'] not in sdk_ids]
            sdk_answered = {question.id_of_question for question in questions if question.already_forecasted}
            conflicts = [row['question_id'] for row in raw_open
                         if row['question_id'] in sdk_answered and row['already_forecasted'] is False]
            unknown = [row['question_id'] for row in raw_open
                       if row['question_id'] in sdk_answered and row['already_forecasted'] is None]
            audit.update(data, status='mismatch' if missing or conflicts or unknown else 'matched',
                         missing_question_ids=missing, forecast_evidence_mismatches=conflicts,
                         forecast_evidence_unknown=unknown)
            inventory_open.extend(raw_open)
        except Exception as exc:
            audit.update(status='failed', error_type=type(exc).__name__)
        result['retrieval_audit'].append(audit)
    result['question_windows'] = [
        question_window(question, source)
        for source, questions in ((result['targets'][0], primary), (FUTUREEVAL, seasonal))
        for question in questions
    ]
    selected, skips = select_eligible_questions(primary, seasonal, limit=12 if mode == 'tournament' else 1)
    result['skips'] = [asdict(record) for record in skips]
    result['selected'] = len(selected)
    # Filtering above already excludes prior forecasts; no human selects a forecast.
    bot.skip_previously_forecasted_questions = False
    for question in selected:
        # Only provider-directed availability can pause the free route.
        if budget is not None and not budget.can_request:
            result['skips'].append({'question_id': question.id_of_question,
                                    'source': 'selected', 'reason': 'provider_paused'})
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
    answered = {row['question_id'] for row in result['question_windows'] if row['already_forecasted']}
    answered.update(row['question_id'] for row in result['outcomes'] if row['status'] == 'submitted')
    answered.update(row['question_id'] for row in inventory_open if row['already_forecasted'])
    evidence_conflicts = {qid for audit in result['retrieval_audit']
                         for qid in audit.get('forecast_evidence_mismatches', [])}
    evidence_unknown = {qid for audit in result['retrieval_audit']
                        for qid in audit.get('forecast_evidence_unknown', [])}
    answered.difference_update(evidence_conflicts | evidence_unknown)
    reasons = {row['question_id']: row['reason'] for row in result['skips'] if row['reason'] != 'duplicate'}
    reasons.update({row['question_id']: row['status'] for row in result['outcomes'] if row['status'] != 'submitted'})
    pending = {}
    for row in result['question_windows']:
        question_id = row['question_id']
        if question_id not in answered and question_id not in pending:
            pending[question_id] = {**row, 'reason': reasons.get(question_id, 'not_submitted')}
    for row in inventory_open:
        question_id = row['question_id']
        if question_id in evidence_conflicts:
            pending[question_id] = {**row, 'reason': 'forecast_evidence_mismatch'}
        elif question_id in evidence_unknown:
            pending[question_id] = {**row, 'reason': 'forecast_evidence_unknown'}
        if question_id not in answered and question_id not in pending:
            pending[question_id] = {**row, 'reason': 'retrieval_missing'}
    result['pending_questions'] = list(pending.values())
    result['needs_attention'] = bool(pending or result['fetch_errors'] or any(
        audit['status'] != 'matched' for audit in result['retrieval_audit']))
    result['status'] = ('partial_failure' if result['submitted'] else 'failed') if result['failed_or_unconfirmed'] else ('completed' if reports else ('provider_paused' if selected else 'no_new_questions'))
    if result['fetch_errors'] and not reports:
        result['status'] = 'fetch_failed'
    elif result['needs_attention'] and result['status'] in ('completed', 'no_new_questions', 'provider_paused'):
        result['status'] = 'attention_required'
    result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    return reports, result
