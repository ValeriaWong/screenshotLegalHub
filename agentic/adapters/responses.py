"""Responses function-tool bridge. Does not implement a model inference API."""
import json
from typing import Literal
from pydantic import Field, ValidationError
from ..primitives import StrictModel
from ..contracts import HarnessError, digest
from ..context import bounded
from .generic import GenericAdapter

class FunctionCall(StrictModel):
    type: Literal['function_call']
    call_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=64)
    arguments: str = Field(max_length=65536)
    id: str | None = None
    status: Literal['in_progress', 'completed', 'incomplete'] | None = None

class ResponsesAdapter:
    def __init__(self, runtime, principal, *, scope_id):
        if not isinstance(scope_id, str) or not 1 <= len(scope_id) <= 128:
            raise HarnessError('INVALID_SCOPE')
        self.generic, self.principal, self.scope_id = GenericAdapter(runtime), principal, scope_id

    def tools(self):
        # Explicit non-strict permits optional properties in existing workflow schemas.
        # The runtime always performs strict local validation regardless of model support.
        return [dict(type='function', strict=False, **d) for d in self.generic.definitions()]

    async def handle_call(self, item):
        raw = item.model_dump(exclude_none=True) if hasattr(item, 'model_dump') else item
        try:
            call = FunctionCall.model_validate(raw, strict=True)
        except ValidationError:
            raise HarnessError('INVALID_FUNCTION_CALL') from None
        if call.status in {'in_progress', 'incomplete'}:
            raise HarnessError('INCOMPLETE_FUNCTION_CALL')
        try:
            arguments = json.loads(call.arguments)
            if not isinstance(arguments, dict):
                raise HarnessError('INVALID_ARGUMENTS')
            bounded(arguments, self.generic.runtime.limits)
            key = digest([self.principal.subject, self.scope_id, call.call_id])
            result = await self.generic.invoke(call.name, arguments, self.principal, idempotency_key=key)
            payload = dict(ok=True, data=result)
        except (json.JSONDecodeError, RecursionError):
            payload = dict(ok=False, error=HarnessError('INVALID_ARGUMENTS').info.model_dump())
        except HarnessError as error:
            payload = dict(ok=False, error=error.info.model_dump())
        return dict(type='function_call_output', call_id=call.call_id,
                    output=json.dumps(payload, ensure_ascii=False, allow_nan=False))

    async def handle_event(self, event):
        event = event.model_dump(exclude_none=True) if hasattr(event, 'model_dump') else event
        if not isinstance(event, dict):
            raise HarnessError('INVALID_EVENT')
        # The complete item contains name, call_id and final arguments; deltas do not.
        if event.get('type') == 'response.output_item.done':
            item = event.get('item')
            if not isinstance(item, dict):
                raise HarnessError('INVALID_EVENT')
            if item.get('type') == 'function_call':
                return await self.handle_call(item)
        return None

    async def handle_response(self, response):
        value = response.model_dump(exclude_none=True) if hasattr(response, 'model_dump') else response
        output = value.get('output') if isinstance(value, dict) else None
        if not isinstance(output, list) or len(output) > 128:
            raise HarnessError('INVALID_RESPONSE')
        return [await self.handle_call(item) for item in output if isinstance(item, dict) and item.get('type') == 'function_call']
