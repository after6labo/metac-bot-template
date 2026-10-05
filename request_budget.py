"""Observed LLM outcomes and provider-directed pauses, with no local daily cap."""
import json
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


class ProviderPaused(RuntimeError):
    pass


def _rate_limit_headers(error):
    response = getattr(error, 'response', None)
    yield getattr(response, 'headers', None) or getattr(error, 'headers', None) or {}
    # LiteLLM preserves OpenRouter error.metadata.headers in its message even
    # when its response headers omit them. Parse only JSON; never persist it.
    message = str(error)
    start = message.find('{')
    if start < 0:
        return
    try:
        payload, _ = json.JSONDecoder().raw_decode(message[start:])
        headers = payload.get('error', {}).get('metadata', {}).get('headers', {})
    except (ValueError, TypeError, AttributeError):
        return
    if isinstance(headers, dict):
        yield headers


class DailyRequestBudget:
    """Keep the existing state path; counters are diagnostics, never quota usage."""

    def __init__(self, path='run-results/budget.json', now=None):
        self.path = Path(path)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.blocked_for_run = False
        self.session_responses = 0
        self.session_failures = 0
        self.session_tokens = 0
        raw = json.loads(self.path.read_text()) if self.path.exists() else {}
        if not isinstance(raw, dict):
            raise ValueError('Invalid request tracking state')
        day = self.now().date().isoformat()
        self.data = {'schema_version': 2, 'date_utc': day,
                     'successful_responses': 0, 'failed_invocations': 0,
                     'observed_tokens': 0, 'cooldown_until_epoch': 0.0}
        if raw.get('date_utc') == day:
            for field in ('successful_responses', 'observed_tokens', 'failed_invocations'):
                value = raw.get(field, 0)
                if type(value) is not int or value < 0:
                    raise ValueError('Invalid request tracking counter')
                self.data[field] = value
        # Legacy requests_reserved/blocked are intentionally not migrated.
        # A provider's explicit pause, unlike daily metrics, survives midnight.
        if raw.get('schema_version') == 2:
            value = raw.get('cooldown_until_epoch', 0.0)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid provider pause')
            self.data['cooldown_until_epoch'] = value

    @property
    def can_request(self):
        return (not self.blocked_for_run and
                self.now().timestamp() >= self.data['cooldown_until_epoch'])

    def check_available(self):
        if not self.can_request:
            raise ProviderPaused('Free provider is paused; no paid fallback')

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2) + '\n')
        temp.replace(self.path)

    def _roll_day(self):
        day = self.now().date().isoformat()
        if self.data['date_utc'] != day:
            self.data.update(date_utc=day, successful_responses=0,
                             failed_invocations=0, observed_tokens=0)

    def record_response(self, tokens):
        self._roll_day()
        self.session_responses += 1
        self.session_tokens += tokens
        self.data['successful_responses'] += 1
        self.data['observed_tokens'] += tokens
        self.save()

    def record_failure(self, error):
        self._roll_day()
        self.session_failures += 1
        self.data['failed_invocations'] += 1
        # An invocation error is NOT proof a request was sent or quota consumed.
        if getattr(error, 'status_code', None) in (402, 429):
            self.blocked_for_run = True
            now = self.now().timestamp()
            candidates = [self.data['cooldown_until_epoch']]
            for source in _rate_limit_headers(error):
                headers = {str(k).lower(): str(v) for k, v in source.items()}
                retry = headers.get('retry-after')
                if retry:
                    try:
                        candidate = now + float(retry)
                    except ValueError:
                        try:
                            candidate = parsedate_to_datetime(retry).timestamp()
                        except (ValueError, TypeError, OverflowError):
                            candidate = now
                    if math.isfinite(candidate) and candidate > now:
                        candidates.append(candidate)
                reset = headers.get('x-ratelimit-reset')
                if reset:
                    try:
                        # OpenRouter supplies the absolute Unix time in milliseconds.
                        candidate = float(reset) / 1000
                    except ValueError:
                        candidate = now
                    if math.isfinite(candidate) and candidate > now:
                        candidates.append(candidate)
            self.data['cooldown_until_epoch'] = max(candidates)
        self.save()
