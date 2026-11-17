"""Bounded lifecycle. Transport and domain behavior live in adapters/plugins."""
import asyncio
import inspect
import time
from pydantic import BaseModel, ValidationError
from .contracts import (Run, RunRequest, TaskState, Status, TERMINAL, Gate, ReviewResult,
                        HarnessError, ApprovalRequired, ResumeRequest, Limits, digest)
from .context import TaskContext, bounded, project
from .planning import transition, validate_plan
from .review import review

class Runtime:
    def __init__(self, tools, skills, workflows, store, *, limits=None, max_active_runs=16):
        self.tools, self.skills, self.store = tools, skills, store
        self.workflows = {w.name: w for w in workflows}
        if len(self.workflows) != len(workflows) or max_active_runs < 1:
            raise HarnessError('INVALID_REGISTRATION')
        self.limits = limits or Limits()
        self.max_active_runs = max_active_runs
        self._drivers, self._live, self._cancel = {}, {}, set()
        self.closed = False
        store.recover()

    def _auth(self, principal, permission, run=None):
        if permission not in principal.permissions:
            raise HarnessError('PERMISSION_DENIED')
        if run and run.principal.subject != principal.subject:
            raise HarnessError('NOT_FOUND')

    def _fingerprint(self, workflow, plan):
        entries = []
        for task in plan.tasks:
            skill = self.skills.get(task.skill)
            entry = [skill.describe()]
            handlers = [skill.handler, skill.repair, *skill.rules]
            for name in skill.tools:
                tool = self.tools.get(name)
                entry.append(tool.describe()); handlers.append(tool.handler)
            for handler in handlers:
                if handler:
                    try:
                        entry.append(inspect.getsource(handler))
                    except (OSError, TypeError):
                        entry.append(handler.__module__ + '.' + handler.__qualname__)
            entries.append(entry)
        return digest([workflow.name, workflow.version, workflow.input_model.model_json_schema(),
                       plan.model_dump(mode='json'), entries])

    def create_run(self, request, principal):
        if self.closed:
            raise HarnessError('RUNTIME_CLOSED')
        self._auth(principal, 'run:create')
        self._auth(principal, 'run:read')
        request = RunRequest.model_validate(request).model_copy(deep=True)
        bounded(request.input, self.limits)
        if any(v > getattr(self.limits, k) for k, v in request.limits.model_dump().items()):
            raise HarnessError('BUDGET_LIMIT', 'request limits exceed server limits')
        workflow = self.workflows.get(request.workflow)
        if workflow is None:
            raise HarnessError('UNKNOWN_WORKFLOW')
        try:
            value = workflow.input_model.model_validate(request.input, strict=True)
            plan = validate_plan(workflow.plan(value))
            for task in plan.tasks:
                skill = self.skills.get(task.skill)
                skill.input_model.model_validate(task.input, strict=True)
                for name in skill.tools:
                    if not self.tools.get(name).permissions <= principal.permissions:
                        raise HarnessError('PERMISSION_DENIED')
        except ValidationError:
            raise HarnessError('INVALID_INPUT') from None
        bounded(plan.model_dump(mode='json'), request.limits)
        tasks = {t.task_id: TaskState(task_id=t.task_id, stage_id=t.stage_id, dependencies=t.dependencies,
                                     input=t.input, retry_policy=t.retry_policy) for t in plan.tasks}
        run = Run(principal=principal, request=request, plan=plan, tasks=tasks,
                  fingerprint=self._fingerprint(workflow, plan))
        run, created = self.store.create(run)
        if created:
            self.store.save(run, 'run-created')
        if run.status == Status.PENDING:
            self._schedule(run)
        return self.get_run(run.run_id, principal)

    def _schedule(self, run):
        if self.closed:
            raise HarnessError('RUNTIME_CLOSED')
        if run.run_id in self._drivers:
            return
        if len(self._drivers) >= self.max_active_runs:
            raise HarnessError('RATE_LIMITED')
        self._live[run.run_id] = run
        self._drivers[run.run_id] = asyncio.create_task(self._drive(run))

    def get_run(self, run_id, principal):
        run = self.store.get(run_id)
        self._auth(principal, 'run:read', run)
        # The response deliberately excludes persisted identity, input, and plan.
        return dict(run_id=run.run_id, trace_id=run.trace_id, status=run.status.value,
                    result=run.result, error=run.error.model_dump() if run.error else None,
                    usage=run.usage.model_dump(), revision=run.revision,
                    gate=run.gate.model_dump() if run.gate else None,
                    tasks={k: dict(status=v.status.value, review_status=v.review_status, attempts=v.attempts,
                                   repairs=v.repairs, output_digest=v.output_digest,
                                   reviews=[r.model_dump() for r in v.reviews]) for k,v in run.tasks.items()})

    async def wait(self, run_id, principal):
        self.get_run(run_id, principal)
        driver = self._drivers.get(run_id)
        if driver:
            await asyncio.shield(driver)
        return self.get_run(run_id, principal)

    async def stream_events(self, run_id, principal, after=0):
        if not isinstance(after, int) or after < 0:
            raise HarnessError('INVALID_CURSOR')
        self.get_run(run_id, principal)
        cursor = after
        while True:
            for event in self.store.events(run_id, cursor):
                cursor = event.sequence
                yield event.model_dump(mode='json')
            run = self.store.get(run_id)
            if run.status != Status.RUNNING and run.run_id not in self._drivers:
                return
            await asyncio.sleep(0.02)

    async def cancel_run(self, run_id, principal):
        run = self._live.get(run_id) or self.store.get(run_id)
        self._auth(principal, 'run:cancel', run)
        if run.status in TERMINAL:
            return self.get_run(run_id, principal)
        driver = self._drivers.get(run_id)
        if driver and run.status == Status.RUNNING:
            self._cancel.add(run_id)
            driver.cancel()
            await asyncio.gather(driver, return_exceptions=True)
        else:
            # Also works before a scheduled coroutine has entered its try/finally.
            if driver:
                driver.cancel()
                await asyncio.gather(driver, return_exceptions=True)
                self._drivers.pop(run_id, None); self._live.pop(run_id, None)
            transition(run, Status.CANCELLED)
            for task in run.tasks.values():
                if task.status != Status.COMPLETED:
                    task.status = Status.CANCELLED
            self.store.save(run, 'run-cancelled')
        return self.get_run(run_id, principal)

    def resume_run(self, run_id, principal, request=None):
        run = self.store.get(run_id)
        self._auth(principal, 'run:resume', run)
        request = ResumeRequest.model_validate(request or {})
        if run.status not in {Status.WAITING_REVIEW, Status.INTERRUPTED}:
            raise HarnessError('INVALID_STATE')
        if not run.principal.permissions <= principal.permissions or not run.principal.resources <= principal.resources:
            raise HarnessError('PERMISSION_DENIED', 'authorization changed')
        workflow = self.workflows.get(run.request.workflow)
        if workflow is None or self._fingerprint(workflow, run.plan) != run.fingerprint:
            raise HarnessError('VERSION_CONFLICT')
        if run.gate:
            self._auth(principal, 'run:review', run)
            if request.gate_digest != run.gate.digest or request.decision not in {'approve', 'reject'}:
                raise HarnessError('STALE_REVIEW')
            task = run.tasks[run.gate.task_id]
            if request.decision == 'reject':
                task.status = Status.FAILED; task.review_status = 'BLOCKED'
                task.reviews.append(ReviewResult(status='BLOCKED', score=0, reviewer_type='human'))
                for other in run.tasks.values():
                    if other.status == Status.PENDING:
                        other.status = Status.SKIPPED
                transition(run, Status.FAILED)
                run.error = HarnessError('REVIEW_REJECTED').info
                run.gate = None
                self.store.save(run, 'review-rejected', task.task_id)
                return self.get_run(run_id, principal)
            if run.gate.kind == 'output':
                task.status = Status.COMPLETED; task.review_status = 'PASS'
                task.reviews.append(ReviewResult(status='PASS', reviewer_type='human'))
            else:
                run.approvals.append(run.gate.digest); task.status = Status.PENDING
            run.gate = None
            self.store.save(run, 'review-approved', task.task_id)
        elif request.decision is not None or request.gate_digest is not None:
            raise HarnessError('INVALID_INPUT')
        self._schedule(run)
        return self.get_run(run_id, principal)

    def list_skills(self, principal):
        self._auth(principal, 'run:read')
        return self.skills.describe()

    def list_tools(self, principal):
        self._auth(principal, 'run:read')
        return [t for t in self.tools.describe() if set(t['permissions']) <= principal.permissions]

    def _pause(self, run, task, kind, gate_digest, **preview):
        task.status = Status.WAITING_REVIEW
        if kind == 'output':
            task.review_status = 'WAITING_REVIEW'
        run.gate = Gate(task_id=task.task_id, kind=kind, digest=gate_digest, **preview)
        transition(run, Status.WAITING_REVIEW)
        self.store.save(run, 'review-required', task.task_id, kind=kind, gate_digest=gate_digest)

    async def _task(self, run, spec):
        task = run.tasks[spec.task_id]
        skill = self.skills.get(spec.skill)
        has_effect = any(self.tools.get(t).side_effect for t in skill.tools)
        limit = run.request.limits
        while True:
            if task.attempts >= spec.retry_policy.max_attempts * (task.repairs + 1):
                raise HarnessError('RETRY_EXHAUSTED')
            if run.usage.iterations >= limit.max_iterations:
                raise HarnessError('BUDGET_EXHAUSTED')
            stage_key = str(spec.stage_id)
            reserved = min(spec.timeout_seconds, run.plan.stage_timeout_seconds - run.stage_elapsed.get(stage_key, 0),
                           limit.timeout_seconds - run.active_seconds)
            if reserved <= 0:
                raise HarnessError('STAGE_TIMEOUT')
            # Reserve BEFORE execution: a crash cannot reset time/attempt budgets.
            run.active_seconds += reserved
            run.stage_elapsed[stage_key] = run.stage_elapsed.get(stage_key, 0) + reserved
            task.attempts += 1; run.usage.iterations += 1; task.status = Status.RUNNING
            self.store.save(run, 'task-started', task.task_id, attempt=task.attempts, stage_id=spec.stage_id)
            ctx = TaskContext(run, task, self.tools, self.store, skill)
            started = time.monotonic()
            try:
                async with asyncio.timeout(reserved):
                    values = skill.input_model.model_validate(project(['input'], {'input':task.input})['input'], strict=True)
                    handler = skill.repair if task.review_status == 'REWORK' else skill.handler
                    output = await handler(values, ctx)
                    raw = output.model_dump(mode='json') if isinstance(output, BaseModel) else output
                    bounded(raw, limit)
                    value, verdict = await review(skill, raw, ctx)
                    bounded(verdict.model_dump(), limit)
            except ApprovalRequired as approval:
                # Pausing is not a failed attempt; total iteration/time budgets still apply.
                task.attempts -= 1
                self._pause(run, task, 'effect', approval.approval_digest, tool=approval.tool,
                            input=approval.arguments, operation_key=approval.operation_key)
                return
            except TimeoutError:
                raise HarnessError('EFFECT_UNCERTAIN' if has_effect else 'STAGE_TIMEOUT') from None
            except HarnessError as error:
                task.error = error.info
                if (error.info.retryable and type(error).__name__ in spec.retry_policy.retryable_errors
                        and task.attempts < spec.retry_policy.max_attempts * (task.repairs + 1)):
                    self.store.save(run, 'task-retry', task.task_id, error_code=error.info.code)
                    # Bounded by max_attempts; no hidden unlimited retries.
                    await asyncio.sleep(min(spec.retry_policy.backoff * 2 ** (task.attempts-1), 30))
                    continue
                raise
            finally:
                refund = max(0, reserved - (time.monotonic() - started))
                run.active_seconds -= refund; run.stage_elapsed[stage_key] -= refund
                if run.status == Status.WAITING_REVIEW:
                    self.store.save(run, 'task-paused', task.task_id)
            task.output = value if value is not None else raw if isinstance(raw, dict) else None
            task.reviews.append(verdict); task.review_status = verdict.status
            self.store.save(run, 'task-reviewed', task.task_id, review_status=verdict.status, score=verdict.score)
            if verdict.status == 'PASS':
                task.output_digest = digest(task.output)
                task.error = None
                if spec.human_review:
                    self._pause(run, task, 'output', digest([run.run_id, task.task_id, task.output_digest]))
                    return
                task.status = Status.COMPLETED
                self.store.save(run, 'task-completed', task.task_id, output_digest=task.output_digest)
                return
            if verdict.status == 'WAITING_REVIEW':
                # Human review follows deterministic checks and is explicitly represented.
                task.output_digest = digest(task.output)
                self._pause(run, task, 'output', digest([run.run_id, task.task_id, task.output_digest]))
                return
            if verdict.status == 'REWORK' and skill.repair and task.repairs < limit.max_repairs:
                task.repairs += 1
                self.store.save(run, 'task-repair', task.task_id, repair=task.repairs)
                continue
            raise HarnessError('REVIEW_FAILED')

    async def _drive(self, run):
        current = None
        try:
            transition(run, Status.RUNNING)
            self.store.save(run, 'run-started')
            for stage in sorted({t.stage_id for t in run.plan.tasks}):
                pending = {t.task_id: t for t in run.plan.tasks if t.stage_id == stage and run.tasks[t.task_id].status != Status.COMPLETED}
                if not pending:
                    continue
                self.store.save(run, 'stage-started', stage_id=stage)
                while pending:
                    ready = [t for t in pending.values() if all(run.tasks[d].status == Status.COMPLETED for d in t.dependencies)]
                    if not ready:
                        raise HarnessError('INVALID_PLAN')
                    for spec in ready:
                        current = run.tasks[spec.task_id]
                        await self._task(run, spec)
                        if run.status == Status.WAITING_REVIEW:
                            return
                        pending.pop(spec.task_id)
                self.store.save(run, 'stage-completed', stage_id=stage)
            dependencies = {d for t in run.plan.tasks for d in t.dependencies}
            run.result = bounded({k: t.output for k,t in run.tasks.items() if k not in dependencies}, run.request.limits)
            transition(run, Status.COMPLETED)
            self.store.save(run, 'run-completed')
        except asyncio.CancelledError:
            cancelled = run.run_id in self._cancel
            run.approvals = []
            transition(run, Status.CANCELLED if cancelled else Status.INTERRUPTED)
            for task in run.tasks.values():
                if task.status != Status.COMPLETED:
                    task.status = Status.CANCELLED if cancelled else Status.PENDING
            self.store.save(run, 'run-cancelled' if cancelled else 'run-interrupted')
        except Exception as error:
            info = error.info if isinstance(error, HarnessError) else HarnessError('EXECUTION_FAILED').info
            if current:
                current.status = Status.FAILED; current.error = info
            for task in run.tasks.values():
                if task.status == Status.PENDING:
                    task.status = Status.SKIPPED
            transition(run, Status.FAILED); run.error = info
            self.store.save(run, 'run-failed', current.task_id if current else None, error_code=info.code)
        finally:
            self._drivers.pop(run.run_id, None); self._live.pop(run.run_id, None); self._cancel.discard(run.run_id)

    async def close(self):
        self.closed = True
        drivers = list(self._drivers.values())
        for driver in drivers:
            driver.cancel()
        await asyncio.gather(*drivers, return_exceptions=True)
        self._drivers.clear(); self._live.clear()
        self.store.close()
