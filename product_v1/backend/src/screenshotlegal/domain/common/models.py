import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class NodeStatus(StrEnum):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    WAITING_REVIEW = 'WAITING_REVIEW'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    INTERRUPTED = 'INTERRUPTED'

class Entity(BaseModel):
    """Shared wire schema; additional capability fields are explicitly carried in details."""
    id: str
    kind: str
    title: str
    case_id: str = ''
    analysis_run_id: str = ''
    skill_run_id: str = ''
    status: str = 'proposed'
    review_status: str = 'unreviewed'
    source_refs: list[str] = []
    details: dict[str, Any] = {}
    output_digest: str = ''

class SkillResult(StrictModel):
    entities: list[Entity] = []
    warnings: list[str] = []
    requires_review: bool = False

class SkillContext(StrictModel):
    case_id: str
    run_id: str
    projection: dict[str, Any]

class SkillInput(StrictModel):
    values: dict[str, Any]

class ReviewRequest(StrictModel):
    target_id: str
    action: str = Field(pattern='^(verified|edited|rejected|deferred)$')
    output_digest: str
    text: str = ''
    reviewer: str = 'local-user'

class CaseCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=10000)

class CaseRecord(StrictModel):
    id: str
    title: str
    description: str = ''
    created_at: str
    active_analysis_run_id: str | None = None
    owner_id: str | None = None
    members: dict[str, str] = {}
    access_role: str = 'owner'
    summary: str = ''
    notes: str = ''
    revision: int = 0
    updated_at: str | None = None

class RunRequest(StrictModel):
    critical_gate: bool = False
    document_ids: list[str] = Field(default_factory=list,max_length=30)

class Selection(StrictModel):
    matter_pack_id: str = 'cn.civil.private_lending'
    version: str = '1.0.0'

class CompileRequest(StrictModel):
    overrides: dict[str, str] = {}

class GateRequest(StrictModel):
    action: str = Field(pattern='^(approve|reject)$')

class MatrixRow(StrictModel):
    claim: Entity
    element: Entity
    fact: Entity
    burden: Entity | None = None
    supporting: list[Entity] = []
    contradicting: list[Entity] = []
    gaps: list[Entity] = []
    strength: str = 'unknown'

class ProofGraph(StrictModel):
    analysis_run_id: str | None = None
    entities: list[Entity] = []
    edges: list[dict[str, str]] = []
    citation_bindings: list[dict[str, Any]] = []
