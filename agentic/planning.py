"""Bounded static planning and explicit state transitions."""
from dataclasses import dataclass
from typing import Callable
from pydantic import BaseModel
from .contracts import Plan, Status, HarnessError

_TRANSITIONS = {
    Status.PENDING: {Status.RUNNING, Status.CANCELLED},
    Status.RUNNING: {Status.COMPLETED, Status.FAILED, Status.CANCELLED, Status.WAITING_REVIEW, Status.INTERRUPTED},
    Status.WAITING_REVIEW: {Status.RUNNING, Status.FAILED, Status.CANCELLED},
    Status.INTERRUPTED: {Status.RUNNING, Status.CANCELLED, Status.FAILED},
}

def transition(run, target):
    if target not in _TRANSITIONS.get(run.status, set()):
        raise HarnessError('INVALID_STATE')
    run.status = target

def validate_plan(plan: Plan):
    tasks = {t.task_id: t for t in plan.tasks}
    if len(tasks) != len(plan.tasks):
        raise HarnessError('INVALID_PLAN', 'duplicate task id')
    done, active = set(), set()
    def visit(t):
        if t.task_id in active:
            raise HarnessError('INVALID_PLAN', 'dependency cycle')
        if t.task_id in done:
            return
        active.add(t.task_id)
        if len(set(t.dependencies)) != len(t.dependencies):
            raise HarnessError('INVALID_PLAN', 'duplicate dependency')
        for dep in t.dependencies:
            if dep not in tasks or tasks[dep].stage_id > t.stage_id:
                raise HarnessError('INVALID_PLAN', 'missing or backwards stage dependency')
            visit(tasks[dep])
        active.remove(t.task_id)
        done.add(t.task_id)
    for t in plan.tasks:
        visit(t)
    return plan

@dataclass(frozen=True)
class Workflow:
    name: str
    version: str
    input_model: type[BaseModel]
    plan: Callable[[BaseModel], Plan]
    description: str = ''
