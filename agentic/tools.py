"""Atomic operations. Only server-registered trusted implementations run."""
import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Callable
from pydantic import BaseModel, ValidationError
from .primitives import with_retry
from .contracts import HarnessError, ApprovalRequired, RetryPolicy, ToolResult, digest
from .context import bounded

@dataclass(frozen=True)
class Tool:
    name: str
    version: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable
    permissions: frozenset[str] = frozenset()
    description: str = ''
    timeout_seconds: float = 10
    retry_policy: RetryPolicy = field(default_factory=lambda: RetryPolicy(max_attempts=1))
    side_effect: bool = False
    idempotent: bool = False

    def describe(self):
        return dict(name=self.name, version=self.version, description=self.description,
                    input_schema=self.input_model.model_json_schema(), output_schema=self.output_model.model_json_schema(),
                    permissions=sorted(self.permissions), side_effect=self.side_effect, idempotent=self.idempotent,
                    timeout_seconds=self.timeout_seconds, retry_policy=self.retry_policy.model_dump())

class ToolRegistry:
    def __init__(self):
        self._items = {}

    def register(self, tool):
        if tool.name in self._items or not tool.version or not 0 < tool.timeout_seconds <= 3600:
            raise HarnessError('INVALID_REGISTRATION')
        if tool.side_effect and (not tool.idempotent or not inspect.iscoroutinefunction(tool.handler)):
            raise HarnessError('UNSAFE_TOOL', 'write tools require async execution and provider idempotency')
        self._items[tool.name] = tool
        return tool

    def get(self, name):
        if name not in self._items:
            raise HarnessError('UNKNOWN_TOOL')
        return self._items[name]

    def describe(self):
        return [t.describe() for t in self._items.values()]

    async def execute(self, name, arguments, ctx, key):
        tool = self.get(name)
        run = ctx._run
        if not tool.permissions <= ctx.principal.permissions:
            raise HarnessError('PERMISSION_DENIED')
        try:
            values = tool.input_model.model_validate(bounded(arguments, run.request.limits), strict=True)
        except ValidationError:
            raise HarnessError('INVALID_TOOL_INPUT') from None
        cached = ctx._store.call_get(key)
        if cached and cached[0] == 'COMPLETED':
            ctx._store.save(run, 'tool-replayed', ctx.task_id, tool=name, operation_key=key)
            return ToolResult(data=cached[1], operation_key=key)
        if tool.side_effect:
            approval = digest([run.fingerprint, ctx.task_id, name, tool.version, values.model_dump(mode='json'), key])
            if approval not in run.approvals:
                raise ApprovalRequired(approval, name, values.model_dump(mode='json'), key)

        async def operation():
            if run.usage.tool_calls >= run.request.limits.max_tool_calls:
                raise HarnessError('BUDGET_EXHAUSTED')
            run.usage.tool_calls += 1
            ctx._store.save(run, 'tool-started', ctx.task_id, tool=name, operation_key=key)
            ctx._store.call_start(key, run.run_id)
            try:
                async with asyncio.timeout(tool.timeout_seconds):
                    if inspect.iscoroutinefunction(tool.handler):
                        value = await tool.handler(values, ctx, key)
                    else:
                        value = await asyncio.to_thread(tool.handler, values, ctx, key)
                raw = value.model_dump(mode='json') if isinstance(value, BaseModel) else value
                output = tool.output_model.model_validate(bounded(raw, run.request.limits), strict=True).model_dump(mode='json')
            except TimeoutError:
                raise HarnessError('EFFECT_UNCERTAIN' if tool.side_effect else 'TOOL_TIMEOUT') from None
            except ValidationError:
                raise HarnessError('INVALID_TOOL_OUTPUT') from None
            except HarnessError:
                raise
            except Exception:
                raise HarnessError('EFFECT_UNCERTAIN' if tool.side_effect else 'TOOL_FAILED') from None
            ctx._store.call_finish(key, output)
            return output

        async def audit(attempt, result, error, latency):
            ctx._store.save(run, 'tool-failed' if error else 'tool-completed', ctx.task_id,
                            tool=name, operation_key=key, attempt=attempt, latency_seconds=round(latency, 6),
                            error_code=error.info.code if isinstance(error, HarnessError) else None,
                            output_digest=digest(result) if result is not None else None)
        try:
            data = await with_retry(operation, tool.retry_policy, audit)
        except asyncio.CancelledError:
            ctx._store.save(run, 'tool-cancelled', ctx.task_id, tool=name, operation_key=key,
                            effect_uncertain=tool.side_effect)
            raise
        return ToolResult(data=data, operation_key=key)
