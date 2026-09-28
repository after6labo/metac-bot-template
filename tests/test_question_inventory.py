import unittest
from question_inventory import collect_inventory


def post(pid, qid, status='open'):
    return {'id': pid, 'status': status, 'open_time': '2026-09-28T14:00:00Z',
            'scheduled_close_time': '2026-09-28T17:00:00Z',
            'question': {'id': qid, 'status': status, 'type': 'binary',
                         'my_forecasts': {'history': []}, 'description': 'not retained'}}


class Transport:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.offsets = []

    def __call__(self, url, **kwargs):
        self.offsets.append(kwargs['params']['offset'])
        if url != 'https://www.metaculus.com/api/posts/':
            raise AssertionError('Wrong destination')
        if kwargs['params']['tournaments'] != 'minibench':
            raise AssertionError('Wrong target')
        if kwargs['params'].get('with_cp') != 'true' or kwargs['params'].get('include_conditional_cps') != 'true':
            raise AssertionError('Missing forecast metadata query flags')
        payload = next(self.pages)
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return payload
        return Response()


class InventoryTests(unittest.TestCase):
    def collect(self, pages):
        return collect_inventory('minibench', 'test-only-credential', get=Transport(pages))

    def test_raw_metadata_keeps_closed_and_open_without_sdk_type_filters(self):
        p = post(1, 11)
        p['question']['type'] = 'future_unknown_type'
        result = self.collect([{'results': [p, post(2, 12, 'closed')], 'next': None}])
        self.assertTrue(result['complete'])
        self.assertEqual([r['question_id'] for r in result['questions']], [11, 12])
        self.assertEqual(result['questions'][0]['close_time_utc'], '2026-09-28T17:00:00+00:00')
        self.assertNotIn('description', str(result))
        self.assertNotIn('test-only-credential', str(result))

    def test_next_page_is_followed_even_if_first_page_is_short(self):
        transport = Transport([{'results': [post(1, 11)], 'next': 'page2'},
                               {'results': [post(2, 12)], 'next': None}])
        result = collect_inventory('minibench', 'test-only-credential', get=transport)
        self.assertEqual([r['question_id'] for r in result['questions']], [11, 12])
        self.assertEqual(transport.offsets, [0, 1])

    def test_incomplete_or_repeated_pages_are_not_empty_success(self):
        for pages in ([{'count': 2, 'results': [post(1, 11)], 'next': None}],
                      [{'results': [post(1, 11)], 'next': 'more'}, {'results': [post(1, 11)], 'next': None}],
                      [{'results': [], 'next': 'more'}], [{'detail': 'not a result list'}]):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                self.collect(pages)

    def test_group_members_and_conditional_use_sdk_identity_without_content_filters(self):
        group = {'id': 1, 'status': 'open', 'group_of_questions': {'questions': [post(1, 11)['question'], post(1, 12)['question']]}}
        conditional = {'id': 2, 'status': 'open', 'conditional': {'id': 22,
            'question_yes': post(2, 23)['question'], 'question_no': post(2, 24)['question']}}
        result = self.collect([{'results': [group, conditional], 'next': None}])
        self.assertEqual([r['question_id'] for r in result['questions']], [11, 12, 22])

    def test_only_recognized_notebooks_are_nonquestions(self):
        self.assertEqual(self.collect([{'results': [{'id': 1, 'notebook': {}}], 'next': None}])['questions'], [])
        with self.assertRaises(ValueError):
            self.collect([{'results': [{'id': 2, 'new_unknown_structure': {}}], 'next': None}])

    def test_verified_previous_forecast_and_actual_deadline_preserved(self):
        p = post(1, 11)
        p['question']['my_forecasts']['history'] = [{'forecast_values': 'never retained'}]
        p['actual_close_time'] = '2026-09-28T16:00:00Z'
        result = self.collect([{'results': [p], 'next': None}])
        self.assertTrue(result['questions'][0]['already_forecasted'])
        self.assertEqual(result['questions'][0]['close_time_utc'], '2026-09-28T16:00:00+00:00')
        self.assertNotIn('forecast_values', str(result))

    def test_absent_forecast_metadata_is_unknown_not_confirmed_unanswered(self):
        for malformed in ('missing', {}, {'history': 'invalid'}, 123):
            p = post(1, 11)
            if malformed == 'missing':
                del p['question']['my_forecasts']
            else:
                p['question']['my_forecasts'] = malformed
            with self.subTest(malformed=malformed):
                result = self.collect([{'results': [p], 'next': None}])
                self.assertIsNone(result['questions'][0]['already_forecasted'])

    def test_explicit_null_forecasts_is_no_previous_forecast(self):
        p = post(1, 11)
        p['question']['my_forecasts'] = None
        result = self.collect([{'results': [p], 'next': None}])
        self.assertIs(result['questions'][0]['already_forecasted'], False)


if __name__ == '__main__':
    unittest.main()
