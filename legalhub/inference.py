"""Bounded provider retries with preserved attempts and no credential logging."""
from datetime import datetime, timezone
import time
import requests
from legalhub import benchmark as b


def request(model, key, prompt, paths, retries=2, sleeper=time.sleep):
    attempts = []
    started = time.monotonic()
    result = None
    for number in range(retries + 1):
        tick = time.monotonic()
        attempt = {'number': number + 1, 'started_at': datetime.now(timezone.utc).isoformat()}
        retryable = False
        try:
            result = b.infer_detailed(model, key, prompt, paths)
            attempt.update(http_status=result['http_status'], status='response',
                           latency_seconds=result['latency_seconds'], usage=result.get('usage', {}),
                           response_id=result.get('response_id'), request_id=result.get('request_id'))
        except b.ProviderHTTPError as error:
            attempt.update(status='error', http_status=error.http_status, provider_error=error.provider_error)
            retryable = error.http_status in (408, 429, 500, 502, 503, 504)
            detail = str(error.provider_error or {}).casefold()
            if error.http_status==429 and any(x in detail for x in ('insufficient balance','exceeded_current_quota_error','billing hard limit')):
                retryable = False
        except (requests.Timeout, requests.ConnectionError) as error:
            attempt.update(status='error', error_type=type(error).__name__)
            retryable = True
        except Exception as error:
            attempt.update(status='error', error_type=type(error).__name__)
        attempt.setdefault('latency_seconds', time.monotonic() - tick)
        attempts.append(attempt)
        if result is not None or not retryable or number == retries:
            break
        sleeper(min(30, (5 if attempt.get('http_status') == 429 else 2) * 2 ** number))
    row = dict(result or {'status': 'error'})
    row.update(attempts=attempts, first_attempt_success=attempts[0]['status'] == 'response',
               elapsed_seconds=time.monotonic() - started)
    if result is None:
        row.update({k: v for k, v in attempts[-1].items() if k in ('http_status', 'error_type', 'provider_error')})
    return row


def validate_answer(answer, task):
    if task['track'] == 'screening_bundle':
        spaces = task['answer_spaces']
        return (isinstance(answer, dict) and set(answer) == set(spaces)
                and all(isinstance(answer[k], str) and answer[k] in options for k, options in spaces.items()))
    if task['track'] == 'case_choice':
        return (isinstance(answer, list) and all(isinstance(x, str) and x in task['options'] for x in answer)
                and len(answer) == len(set(answer)))
    return isinstance(answer, str)


def predict(model, key, task, retries=2):
    for path, digest in zip(task['images'], task['image_hashes']):
        if b.sha(b.ROOT / path) != digest:
            raise ValueError('Frozen image changed')
    row = {'id': task['id'], 'track': task['track'], 'case_id': task['case_id']}
    row.update(request(model, key, task['prompt'], [b.ROOT / x for x in task['images']], retries))
    if row.get('http_status') == 200:
        try:
            row['answer'] = b.parse_answer(row['raw'])
            row['status'] = 'ok' if validate_answer(row['answer'], task) else 'invalid_answer'
        except (ValueError, TypeError):
            row['status'] = 'invalid_format'
        if row.get('finish_reason') == 'length':
            row['status'] = 'truncated'
    return row
