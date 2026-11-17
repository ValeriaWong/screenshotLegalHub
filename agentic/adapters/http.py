"""Optional FastAPI composition. Server configuration owns authentication."""
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import hmac
import inspect
import json
import time
from fastapi import FastAPI, Depends, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from ..report import render_report
from ..contracts import RunRequest, ResumeRequest, Principal, HarnessError
from .dify import DifyAdapter
from .responses import ResponsesAdapter, FunctionCall

_HTTP_CODES = {
    'UNAUTHENTICATED':401, 'PERMISSION_DENIED':403, 'NOT_FOUND':404,
    'IDEMPOTENCY_CONFLICT':409, 'INVALID_STATE':409, 'VERSION_CONFLICT':409,
    'STALE_REVIEW':409, 'RATE_LIMITED':429, 'BODY_TOO_LARGE':413,
}

class TokenAuth:
    """For service tokens only; inject existing AuthService for interactive users."""
    def __init__(self, tokens: dict[str, Principal]):
        if not tokens or any(len(token) < 24 for token in tokens):
            raise HarnessError('INVALID_AUTH_CONFIG')
        self._tokens = dict(tokens)

    def __call__(self, authorization):
        if not authorization or not authorization.startswith('Bearer '):
            raise HarnessError('UNAUTHENTICATED')
        supplied = authorization[7:].encode()
        for token, principal in self._tokens.items():
            if hmac.compare_digest(supplied, token.encode()):
                return principal
        raise HarnessError('UNAUTHENTICATED')

def create_app(runtime, authenticate, *, base_url='http://127.0.0.1:18440', requests_per_minute=120):
    if not callable(authenticate) or requests_per_minute < 1:
        raise HarnessError('INVALID_AUTH_CONFIG')
    dify = DifyAdapter(runtime)
    openapi = dify.openapi(base_url)
    counters = defaultdict(deque)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await runtime.close()

    app = FastAPI(title='Agentic Harness', version='0.2.0', lifespan=lifespan)

    @app.exception_handler(HarnessError)
    async def harness_error(request, error):
        return JSONResponse(status_code=_HTTP_CODES.get(error.info.code,422), content={'error':error.info.model_dump()})

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return JSONResponse(status_code=422, content={'error':HarnessError('INVALID_INPUT').info.model_dump()})

    @app.middleware('http')
    async def body_limit(request, call_next):
        # Read bounded chunks before FastAPI/Pydantic; never echo validation inputs.
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > runtime.limits.max_context_bytes:
                return JSONResponse(status_code=413, content={'error':HarnessError('BODY_TOO_LARGE').info.model_dump()})
            chunks.append(chunk)
        request._body = b''.join(chunks)
        return await call_next(request)

    async def principal(authorization: str | None = Header(default=None)):
        value = authenticate(authorization)
        if inspect.isawaitable(value):
            value = await value
        value = Principal.model_validate(value)
        queue = counters[value.subject]; current = time.monotonic()
        while queue and current-queue[0] >= 60:
            queue.popleft()
        if len(queue) >= requests_per_minute:
            raise HarnessError('RATE_LIMITED')
        queue.append(current)
        return value

    @app.post('/runs', status_code=202, operation_id='create_run')
    async def create_run(body: RunRequest, identity=Depends(principal)):
        return runtime.create_run(body, identity)

    @app.get('/runs/{run_id}', operation_id='get_run')
    async def get_run(run_id: str, identity=Depends(principal)):
        return runtime.get_run(run_id, identity)

    @app.post('/runs/{run_id}/cancel', operation_id='cancel_run')
    async def cancel(run_id: str, identity=Depends(principal)):
        return await runtime.cancel_run(run_id, identity)

    @app.post('/runs/{run_id}/resume', operation_id='resume_run')
    async def resume(run_id: str, body: ResumeRequest, identity=Depends(principal)):
        return runtime.resume_run(run_id, identity, body)

    @app.get('/runs/{run_id}/events', operation_id='stream_events')
    async def events(run_id: str, after: int=0, last_event_id: str | None=Header(default=None), identity=Depends(principal)):
        runtime.get_run(run_id, identity)
        try:
            cursor = int(last_event_id) if last_event_id is not None else after
            if cursor < 0:
                raise ValueError()
        except ValueError:
            raise HarnessError('INVALID_CURSOR') from None
        async def stream():
            async for event in runtime.stream_events(run_id, identity, cursor):
                yield 'id: '+str(event['sequence'])+'\nevent: '+event['type']+'\ndata: '+json.dumps(event,ensure_ascii=False)+'\n\n'
        return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control':'no-cache'})

    @app.get('/runs/{run_id}/report.html', response_class=HTMLResponse, operation_id='get_report')
    async def report_html(run_id: str, identity=Depends(principal)):
        run = runtime.get_run(run_id, identity)
        events = [e.model_dump(mode='json') for e in runtime.store.events(run_id)]
        return HTMLResponse(render_report(run, events), headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.get('/skills', operation_id='list_skills')
    async def skills(identity=Depends(principal)):
        return runtime.list_skills(identity)

    @app.get('/tools', operation_id='list_tools')
    async def tools(identity=Depends(principal)):
        return runtime.list_tools(identity)

    @app.get('/adapters/responses/tools')
    async def responses_tools(identity=Depends(principal)):
        runtime._auth(identity, 'run:read')
        return ResponsesAdapter(runtime, identity, scope_id='discovery').tools()

    @app.post('/adapters/responses/calls')
    async def responses_call(body: FunctionCall, x_harness_scope: str=Header(min_length=1,max_length=128), identity=Depends(principal)):
        return await ResponsesAdapter(runtime, identity, scope_id=x_harness_scope).handle_call(body)

    @app.get('/adapters/dify/openapi.json')
    async def dify_schema(identity=Depends(principal)):
        return openapi

    @app.post('/adapters/dify/{operation}')
    async def dify_call(operation: str, body: dict, idempotency_key: str=Header(min_length=1,max_length=128), identity=Depends(principal)):
        return await dify.invoke(operation, body, identity, idempotency_key=idempotency_key)

    return app
