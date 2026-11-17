"""Small standalone JSON contracts and execution utilities; no application imports."""
import asyncio
import copy
import hashlib
import json
import time
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class RetryPolicy(StrictModel):
    max_attempts: int = Field(default=2, ge=1, le=5)
    retryable_errors: list[str] = Field(default_factory=lambda: ['TransientError', 'JSONDecodeError'])
    backoff: float = Field(default=0.05, ge=0, le=30, allow_inf_nan=False)

def digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def project(needs, state):
    return {name: copy.deepcopy(state[name]) for name in needs}

async def with_retry(operation, policy, on_attempt):
    for attempt in range(1, policy.max_attempts + 1):
        started = time.monotonic()
        try:
            result = await operation()
        except Exception as error:
            await on_attempt(attempt, None, error, time.monotonic() - started)
            if attempt >= policy.max_attempts or type(error).__name__ not in policy.retryable_errors:
                raise
            await asyncio.sleep(policy.backoff * 2 ** (attempt - 1))
        else:
            await on_attempt(attempt, result, None, time.monotonic() - started)
            return result
