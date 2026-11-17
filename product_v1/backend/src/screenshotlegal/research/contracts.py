"""Versioned public contracts for research products. No case/private DB dependencies."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

CONTRACT = 'research.v1'
RENDERER = 'pillow-chat.v4'

def now():
    return datetime.now(timezone.utc).isoformat()

def uid(prefix):
    return prefix + '.' + uuid4().hex

def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def digest(value):
    return hashlib.sha256((value if isinstance(value, bytes) else dumps(value).encode())).hexdigest()

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Message(Contract):
    id: str = Field(min_length=1, max_length=200)
    speaker: str = Field(default='unknown', max_length=200)
    text: str = Field(min_length=1, max_length=20000)
    timestamp: str | None = None
    source_refs: list[dict] = Field(default_factory=list)
    origin_type: Literal["unknown", "verbatim_quote", "judgment_paraphrase", "synthetic_completion", "unsupported"] = "unknown"
    source_quote: str = ""
    speaker_basis: Literal["source", "simulated", "unknown"] = "unknown"
    time_basis: Literal["source", "simulated", "unknown"] = "unknown"

class Question(Contract):
    id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=10000)
    task_type: str = Field(default='qa', max_length=200)
    answer: str | None = Field(default=None, max_length=20000)
    gold: bool = False
    message_ids: list[str] = Field(default_factory=list)

class Content(Contract):
    title: str = Field(min_length=1, max_length=500)
    category: str = Field(default='chat', min_length=1, max_length=300)
    language: str = Field(default='zh', max_length=30)
    platform: str = Field(default='generic', max_length=100)
    kind: Literal['synthetic', 'original'] = 'synthetic'
    source_text: str = Field(default='', max_length=2000000)
    source_refs: list[dict] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list, max_length=1000)
    questions: list[Question] = Field(default_factory=list, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=100)
    original_assets: list[dict] = Field(default_factory=list, max_length=500)
    metadata: dict = Field(default_factory=dict)
    visual_role: Literal['auto','original','synthetic_render','transcription_overlay'] = 'auto'
    original_layout: list[dict] = Field(default_factory=list,max_length=500)

    @model_validator(mode='after')
    def references(self):
        mids = [m.id for m in self.messages]
        qids = [q.id for q in self.questions]
        if len(set(mids)) != len(mids) or len(set(qids)) != len(qids):
            raise ValueError('Message and question IDs must be unique')
        for q in self.questions:
            if set(q.message_ids) - set(mids):
                raise ValueError('Question refers to unknown message IDs')
            if q.gold and not q.answer:
                raise ValueError('Gold question requires an answer')
        return self

class RenderParams(Contract):
    width: int = Field(default=760, ge=400, le=1600)
    page_height: int = Field(default=1100, ge=500, le=2400)
    font_size: int = Field(default=24, ge=16, le=48)

class Region(Contract):
    message_id: str = Field(min_length=1,max_length=200)
    bbox: tuple[float,float,float,float]

class PageLayout(Contract):
    page: int = Field(ge=1,le=10000)
    width: int = Field(ge=100,le=10000)
    height: int = Field(ge=100,le=20000)
    boxes: list[Region] = Field(default_factory=list,max_length=2000)

    @model_validator(mode='after')
    def bounds(self):
        import math
        for box in self.boxes:
            x1,y1,x2,y2=box.bbox
            if not all(math.isfinite(n) for n in box.bbox) or not (0 <= x1 < x2 <= self.width and 0 <= y1 < y2 <= self.height) or x2-x1<8 or y2-y1<8:
                raise ValueError('Bounding box must be finite, inside its page and at least 8 pixels wide/high')
        return self

class SampleCreate(Contract):
    dataset: str = Field(min_length=1, max_length=200)
    content: Content
    render: RenderParams = Field(default_factory=RenderParams)
    layout: list[PageLayout] = Field(default_factory=list,max_length=1000)
    note: str = Field(min_length=1, max_length=10000)
    idempotency_key: str = Field(min_length=1, max_length=200)

class SampleEdit(Contract):
    content: Content
    expected_revision: int = Field(ge=1)
    note: str = Field(min_length=1, max_length=10000)
    render: RenderParams = Field(default_factory=RenderParams)
    layout: list[PageLayout] | None = Field(default=None,max_length=1000)
    layout_manifest_id: str | None = None
    coordinates_unlocked: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)

class RendererUpgrade(Contract):
    expected_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1,max_length=200)

class DraftSave(Contract):
    base_revision: int = Field(ge=1)
    expected_version: int = Field(ge=0)
    draft_id: str = Field(min_length=1, max_length=200)
    content: dict

class PromptSave(Contract):
    name: str = Field(min_length=1, max_length=200)
    markdown: str = Field(min_length=1, max_length=100000)
    note: str = Field(min_length=1, max_length=10000)
    expected_version: int = Field(ge=0)
    feedback_ids: list[str] = Field(default_factory=list, max_length=200)
    based_on_id: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=200)

class CommentSave(Contract):
    revision: int = Field(ge=1)
    message_id: str | None = None
    body: str = Field(min_length=1,max_length=30000)
    use_for_generation: bool = True
    applicability: Literal['revision','source'] = 'revision'
    manifest_id: str | None = None
    page: int | None = Field(default=None,ge=1)
    bbox: tuple[float,float,float,float] | None = None
    supersedes: str | None = None
    idempotency_key: str = Field(min_length=1,max_length=200)

class CommentProcess(Contract):
    expected_event_id: str | None = None
    status: Literal['open','adopted','resolved','rejected','withdrawn']
    reason: str = Field(min_length=1,max_length=10000)
    candidate_sample_id: str | None = None
    candidate_revision: int | None = Field(default=None,ge=1)
    idempotency_key: str = Field(min_length=1,max_length=200)

class QualitySave(Contract):
    review_scope: Literal['text','visual','both'] = 'both'
    manifest_id: str | None = None
    content_hash: str | None = None
    confirm_gold: bool = False
    rubric_id: str = Field(default='human.v1',min_length=1,max_length=200)
    revision: int = Field(ge=1)
    verdict: Literal['pass', 'revise', 'reject', 'pending']
    score: float | None = Field(default=None, ge=0, le=100)
    dimensions: dict[str, float] = Field(default_factory=dict)
    findings: str = Field(default='', max_length=30000)
    suggestions: str = Field(default='', max_length=30000)
    process: str = Field(default='', max_length=30000)
    supersedes: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=200)

    @model_validator(mode='after')
    def valid_dimensions(self):
        import math
        if any(not math.isfinite(value) or not 0 <= value <= 100 for value in self.dimensions.values()):
            raise ValueError('Dimension scores must be finite values between 0 and 100')
        return self

class QualityRun(Contract):
    coverage: Literal['text','visual','multimodal'] = 'text'
    manifest_id: str | None = None
    revision: int = Field(ge=1)
    prompt_id: str
    model_id: str
    idempotency_key: str = Field(min_length=1, max_length=200)

class BatchCreate(Contract):
    name: str = Field(min_length=1, max_length=200)
    dataset: str = Field(min_length=1, max_length=200)
    source_sample_id: str
    source_revision: int = Field(ge=1)
    prompt_id: str
    model_id: str = 'demo'
    count: int = Field(default=1, ge=1, le=50)
    language: str = Field(default='zh', max_length=30)
    platform: str = Field(default='generic', max_length=100)
    task_type: str = Field(default='qa', max_length=200)
    constraints: str = Field(default='', max_length=30000)
    use_review_feedback: bool = True
    feedback_ids: list[str] | None = Field(default=None,max_length=500)
    template: Literal['chat.v1'] = 'chat.v1'
    seed: int = 42
    render: RenderParams = Field(default_factory=RenderParams)
    idempotency_key: str = Field(min_length=1, max_length=200)

class ReleaseCreate(Contract):
    name: str = Field(min_length=1, max_length=200)
    sample_ids: list[str] = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=200)

class EvaluationCreate(Contract):
    name: str = Field(min_length=1, max_length=200)
    release_id: str
    model_ids: list[str] = Field(min_length=1, max_length=10)
    mode: Literal['text', 'image', 'multimodal', 'multi_image'] = 'text'
    sample_ids: list[str] = Field(default_factory=list, max_length=500)
    category: str = ''
    batch_id: str = ''
    tags: list[str] = Field(default_factory=list)
    task_type: str = ''
    sample_size: int | None = Field(default=None, ge=1, le=500)
    seed: int = 42
    concurrency: int = Field(default=2, ge=1, le=8)
    max_calls: int = Field(default=100, ge=1, le=10000)
    idempotency_key: str = Field(min_length=1, max_length=200)
