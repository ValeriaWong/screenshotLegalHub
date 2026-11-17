import math
from pydantic import Field, model_validator
from screenshotlegal.domain.common.models import StrictModel

class SourceRef(StrictModel):
    id: str
    evidence_id: str
    image_id: str | None = None
    evidence_page: int | None = Field(default=None, ge=1)
    message_id: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    raw_bbox: tuple[float, float, float, float] | None = None
    raw_coordinate_space: str = 'pixels'
    quote: str = ''

def validate_bbox(bbox, size):
    if len(bbox) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in bbox):
        raise ValueError('Invalid pixel bbox')
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= size[0] and 0 <= y1 < y2 <= size[1]):
        raise ValueError('BBox outside original image')

class EvidenceItem(StrictModel):
    id: str
    case_id: str
    filename: str
    mime_type: str
    sha256: str
    storage_path: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    kind: str = 'image'

class Message(StrictModel):
    id: str
    evidence_id: str
    text: str
    speaker: str = 'unknown'
    timestamp: str | None = None
    event_type: str = 'other'
    source_refs: list[str] = Field(min_length=1)

class NormalizedPerceptionResult(StrictModel):
    messages: list[Message]
    source_refs: list[SourceRef]
    warnings: list[str] = []

    @model_validator(mode='after')
    def grounded(self):
        refs = {r.id: r for r in self.source_refs}
        for msg in self.messages:
            for rid in msg.source_refs:
                if rid not in refs or refs[rid].evidence_id != msg.evidence_id or refs[rid].message_id != msg.id:
                    raise ValueError('Unresolved message source')
                if refs[rid].quote not in msg.text:
                    raise ValueError('Quote differs from transcription')
        return self
