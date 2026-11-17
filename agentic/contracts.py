"""Versioned wire contracts; no business or transport dependencies."""
from enum import StrEnum
import re
from typing import Any, Annotated, Literal
from uuid import uuid4
from pydantic import Field, ConfigDict
from .primitives import StrictModel, digest, now, RetryPolicy

ID = Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[a-zA-Z0-9_.:-]+$')]

class Status(StrEnum):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    WAITING_REVIEW = 'WAITING_REVIEW'
    INTERRUPTED = 'INTERRUPTED'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'
    SKIPPED = 'SKIPPED'

TERMINAL = {Status.COMPLETED, Status.FAILED, Status.CANCELLED}

class ErrorInfo(StrictModel):
    code: str
    message: str
    retryable: bool = False

class HarnessError(Exception):
    def __init__(self, code, message=None, retryable=False):
        code = code if re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', str(code)) else 'EXECUTION_FAILED'
        self.info = ErrorInfo(code=code, message=code.replace('_', ' ').lower(), retryable=retryable)
        super().__init__(message or self.info.message)

class TransientError(HarnessError):
    def __init__(self):
        super().__init__('TOOL_TRANSIENT', retryable=True)

class ApprovalRequired(HarnessError):
    def __init__(self, approval_digest, tool, arguments, operation_key):
        super().__init__('APPROVAL_REQUIRED')
        self.approval_digest, self.tool = approval_digest, tool
        self.arguments, self.operation_key = arguments, operation_key

class Principal(StrictModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    subject: ID
    permissions: frozenset[str] = frozenset()
    resources: frozenset[str] = frozenset()

class Limits(StrictModel):
    max_iterations: int = Field(default=24, ge=1, le=1000)
    max_repairs: int = Field(default=2, ge=0, le=10)
    max_tool_calls: int = Field(default=32, ge=0, le=10000)
    max_model_calls: int = Field(default=0, ge=0, le=1000)
    max_tokens: int = Field(default=0, ge=0, le=10000000)
    max_cost: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    max_context_bytes: int = Field(default=1000000, ge=128, le=10000000)
    max_context_tokens: int = Field(default=1000000, ge=128, le=10000000)
    timeout_seconds: float = Field(default=60, gt=0, le=3600, allow_inf_nan=False)

class Usage(StrictModel):
    iterations: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    unsettled_model_calls: int = 0
    tokens: int = 0
    cost: float = 0

class ReviewResult(StrictModel):
    status: Literal['PASS', 'REWORK', 'BLOCKED', 'WAITING_REVIEW']
    score: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    findings: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    reviewer_type: Literal['schema', 'rule', 'human', 'llm'] = 'rule'

class TaskSpec(StrictModel):
    task_id: ID
    stage_id: int = Field(ge=0, le=1000)
    skill: ID
    dependencies: list[ID] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=dict)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout_seconds: float = Field(default=15, gt=0, le=3600, allow_inf_nan=False)
    human_review: bool = False

class Plan(StrictModel):
    tasks: list[TaskSpec] = Field(min_length=1, max_length=256)
    stage_timeout_seconds: float = Field(default=30, gt=0, le=3600, allow_inf_nan=False)

class TaskState(StrictModel):
    task_id: ID
    stage_id: int
    dependencies: list[ID]
    status: Status = Status.PENDING
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    retry_policy: RetryPolicy
    review_status: str = 'UNREVIEWED'
    reviews: list[ReviewResult] = Field(default_factory=list)
    attempts: int = 0
    repairs: int = 0
    error: ErrorInfo | None = None
    output_digest: str | None = None

class RunRequest(StrictModel):
    workflow: ID
    input: dict[str, Any]
    idempotency_key: ID
    limits: Limits = Field(default_factory=Limits)

class Gate(StrictModel):
    task_id: ID
    kind: Literal['output', 'effect']
    digest: str
    tool: str | None = None
    input: dict[str, Any] | None = None
    operation_key: str | None = None

class Run(StrictModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    principal: Principal
    request: RunRequest
    fingerprint: str
    plan: Plan
    tasks: dict[str, TaskState]
    status: Status = Status.PENDING
    usage: Usage = Field(default_factory=Usage)
    gate: Gate | None = None
    approvals: list[str] = Field(default_factory=list)
    stage_elapsed: dict[str, float] = Field(default_factory=dict)
    active_seconds: float = 0
    result: dict[str, Any] | None = None
    error: ErrorInfo | None = None
    revision: int = 0
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)

class Event(StrictModel):
    run_id: str
    trace_id: str
    sequence: int
    type: str
    task_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now)

class ToolResult(StrictModel):
    data: dict[str, Any]
    operation_key: str

class ResumeRequest(StrictModel):
    decision: Literal['approve', 'reject'] | None = None
    gate_digest: str | None = None
