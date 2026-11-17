"""Scoped execution data and conservative, persisted budget reservations."""
import json
from .primitives import project
from .contracts import HarnessError, digest
from .observability import check_payload

def bounded(value, limits):
    check_payload(value)
    size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8'))
    # UTF-8 bytes are a conservative context estimate, NOT measured provider usage.
    if size > min(limits.max_context_bytes, limits.max_context_tokens):
        raise HarnessError('CONTEXT_LIMIT')
    return value

class TaskContext:
    def __init__(self, run, task, tools, store, spec):
        self.run_id, self.trace_id, self.task_id = run.run_id, run.trace_id, task.task_id
        self.principal = run.principal
        self.dependencies = bounded(project(task.dependencies, {
            k: v.output for k, v in run.tasks.items() if v.status == 'COMPLETED'
        }), run.request.limits)
        self._run, self._task, self._tools, self._store = run, task, tools, store
        self._spec, self._call_number = spec, 0
        self.review = task.reviews[-1] if task.reviews else None
        self.previous_output = project(['output'], {'output':task.output})['output']

    async def call_tool(self, name, arguments):
        if name not in self._spec.tools:
            raise HarnessError('PERMISSION_DENIED', 'skill did not declare tool')
        self._call_number += 1
        key = digest([self.run_id, self.task_id, self._task.repairs, self._call_number,
                      name, self._tools.get(name).version, arguments])
        return await self._tools.execute(name, arguments, self, key)

    def reserve_model(self, max_tokens, max_cost):
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 0:
            raise HarnessError('INVALID_USAGE')
        if not isinstance(max_cost, (int, float)) or not 0 <= max_cost <= 1000:
            raise HarnessError('INVALID_USAGE')
        run, limit = self._run, self._run.request.limits
        if (run.usage.model_calls + 1 > limit.max_model_calls or run.usage.tokens + max_tokens > limit.max_tokens
                or run.usage.cost + max_cost > limit.max_cost):
            raise HarnessError('BUDGET_EXHAUSTED')
        run.usage.model_calls += 1
        run.usage.unsettled_model_calls += 1
        run.usage.tokens += max_tokens
        run.usage.cost += max_cost
        self._store.save(run, 'model-reserved', self.task_id, tokens=max_tokens, cost=max_cost)
        return ModelReservation(self, max_tokens, max_cost)

class ModelReservation:
    def __init__(self, context, tokens, cost):
        self.context, self.tokens, self.cost, self.settled = context, tokens, cost, False

    def settle(self, tokens, cost):
        if self.settled or not isinstance(tokens, int) or isinstance(tokens, bool) or not 0 <= tokens <= self.tokens or not 0 <= cost <= self.cost:
            raise HarnessError('INVALID_USAGE')
        self.settled = True
        ctx = self.context
        ctx._run.usage.unsettled_model_calls -= 1
        ctx._run.usage.tokens -= self.tokens - tokens
        ctx._run.usage.cost -= self.cost - cost
        ctx._store.save(ctx._run, 'model-usage', ctx.task_id, tokens=tokens, cost=cost)
