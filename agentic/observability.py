"""Events contain identifiers and counters, never raw inputs/provider errors."""
import json
import logging
import re
from .contracts import HarnessError

log = logging.getLogger('agentic')
_SECRET_KEY = re.compile(r'(api[_-]?key|password|authorization|cookie|secret|access[_-]?token)', re.I)
_SECRET_VALUE = re.compile(r'(?i)\bBearer\s+\S+|\bsk-[a-zA-Z0-9_-]{12,}')

def check_payload(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if _SECRET_KEY.search(str(key)):
                raise HarnessError('SENSITIVE_CONTEXT', 'credentials must stay in server configuration')
            check_payload(item)
    elif isinstance(value, list):
        for item in value:
            check_payload(item)
    elif isinstance(value, str) and _SECRET_VALUE.search(value):
        raise HarnessError('SENSITIVE_CONTEXT', 'credentials must stay in server configuration')
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        raise HarnessError('INVALID_INPUT', 'payload must be finite JSON') from None

def log_event(event):
    log.info(json.dumps({k: event[k] for k in ('run_id', 'trace_id', 'sequence', 'type', 'task_id')}, ensure_ascii=False))
