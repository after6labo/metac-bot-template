"""Read sanitized tournament metadata independently of SDK selection/parsing."""
from datetime import datetime, timezone


def _utc(value):
    if value is None:
        return None
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Missing timezone in question window')
    return date.astimezone(timezone.utc).isoformat()


def _forecasted(node):
    if 'my_forecasts' not in node:
        return None
    forecasts = node.get('my_forecasts')
    if forecasts is None:
        return False
    if not isinstance(forecasts, dict) or 'history' not in forecasts:
        return None
    history = forecasts['history']
    if history is None:
        return False
    return bool(history) if isinstance(history, list) else None


def _question_rows(post, target):
    if isinstance(post.get('question'), dict):
        nodes = [post['question']]
    elif isinstance(post.get('group_of_questions'), dict):
        nodes = post['group_of_questions']['questions']
        if not isinstance(nodes, list) or not nodes:
            raise ValueError('Missing group members')
    elif isinstance(post.get('conditional'), dict):
        conditional = post['conditional']
        # SDK 0.2.92 represents a conditional as one forecastable object.
        nodes = [{**conditional, 'status': conditional.get('status', post.get('status'))}]
    elif isinstance(post.get('notebook'), dict):
        return []
    else:
        raise ValueError('Unrecognized post structure')
    rows = []
    for node in nodes:
        question_id = node['id']
        status = node.get('status', post.get('status'))
        if not isinstance(question_id, int) or status not in ('open', 'closed', 'resolved', 'upcoming'):
            raise ValueError('Unrecognized question metadata')
        def value(*keys):
            for key in keys:
                if node.get(key) is not None:
                    return node[key]
                if post.get(key) is not None:
                    return post[key]
            return None
        forecasted = _forecasted(node)
        if 'conditional' in post:
            # Require evidence on both forecast branches before declaring answered.
            branches = [_forecasted(node.get(key) or {}) for key in ('question_yes', 'question_no')]
            forecasted = False if False in branches else (None if None in branches else True)
        rows.append({
            'question_id': question_id, 'post_id': post['id'], 'source': target,
            'status': status, 'open_time_utc': _utc(value('open_time')),
            'close_time_utc': _utc(value('actual_close_time', 'scheduled_close_time', 'close_time')),
            'already_forecasted': forecasted,
        })
    return rows


def collect_inventory(target, token, *, get=None):
    if get is None:
        import requests
        get = requests.get
    rows, seen_posts = [], set()
    offset = 0
    for _ in range(10):
        response = get('https://www.metaculus.com/api/posts/',
            params={'tournaments': target, 'statuses': ['open', 'closed', 'resolved', 'upcoming'],
                    'limit': 100, 'offset': offset, 'order_by': '-published_at',
                    'with_cp': 'true', 'include_conditional_cps': 'true'},
            headers={'Authorization': 'Token ' + token, 'Accept-Language': 'en'}, timeout=15)
        response.raise_for_status()
        data = response.json()
        posts = data.get('results')
        if not isinstance(posts, list):
            raise ValueError('Missing result list')
        for post in posts:
            if not isinstance(post.get('id'), int) or post['id'] in seen_posts:
                raise ValueError('Invalid or repeated page')
            seen_posts.add(post['id'])
            rows.extend(_question_rows(post, target))
        offset += len(posts)
        more = bool(data['next']) if 'next' in data else len(posts) == 100
        if not more:
            count = data.get('count')
            if isinstance(count, int) and count != len(seen_posts):
                raise ValueError('Inventory count mismatch')
            return {'complete': True, 'post_count': len(seen_posts), 'questions': rows}
        if not posts:
            raise ValueError('Pagination did not advance')
    raise ValueError('Inventory pagination limit reached')
