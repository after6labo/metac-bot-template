"""Conservative UTC-day quota, persisted before each outbound LLM attempt."""
import json
from datetime import datetime, timezone
from pathlib import Path


class BudgetExhausted(RuntimeError):
    pass


class DailyRequestBudget:
    def __init__(self, path='run-results/budget.json', limit=40, today=None):
        self.path = Path(path)
        self.limit = min(limit, 40)
        self.day = today or datetime.now(timezone.utc).date().isoformat()
        data = json.loads(self.path.read_text()) if self.path.exists() else {}
        if data and (not isinstance(data, dict) or not isinstance(data.get('requests_reserved'), int)
                     or data['requests_reserved'] < 0 or not isinstance(data.get('date_utc'), str)):
            raise ValueError('Invalid persisted request budget')
        self.data = data if data.get('date_utc') == self.day else {
            'date_utc': self.day, 'requests_reserved': 0,
            'successful_responses': 0, 'observed_tokens': 0, 'blocked': False,
        }

    @property
    def remaining(self):
        return 0 if self.data['blocked'] else max(0, self.limit - self.data['requests_reserved'])

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2) + '\n')
        temp.replace(self.path)

    def reserve(self):
        if self.remaining < 1:
            raise BudgetExhausted('Free request budget exhausted; no paid fallback')
        self.data['requests_reserved'] += 1
        self.save()

    def record_response(self, tokens):
        self.data['successful_responses'] += 1
        self.data['observed_tokens'] += tokens
        self.save()

    def block(self):
        self.data['blocked'] = True
        self.save()
