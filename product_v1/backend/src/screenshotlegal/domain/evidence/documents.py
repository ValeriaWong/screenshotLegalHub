"""Parser-independent contracts. No SDK or database imports."""
import math
from typing import Literal
from pydantic import Field, model_validator
from screenshotlegal.domain.common.models import StrictModel

class CoordinateFrame(StrictModel):
    units: Literal['pixels','points','normalized_1000','normalized_01']
    origin: Literal['top_left','bottom_left'] = 'top_left'
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: Literal[0,90,180,270] = 0
    def normalized(self, box: list[float]) -> list[float]:
        if len(box)!=4 or any(not math.isfinite(v) for v in box):
            raise ValueError('Invalid source rectangle')
        x0,y0,x1,y1=box
        x0,x1=sorted([x0,x1]);y0,y1=sorted([y0,y1])
        if not (0<=x0<x1<=self.width and 0<=y0<y1<=self.height): raise ValueError('Rectangle outside source frame')
        if self.origin=='bottom_left': y0,y1=self.height-y1,self.height-y0
        points=[(x/self.width,y/self.height) for x,y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]]
        if self.rotation==90: points=[(1-y,x) for x,y in points]
        elif self.rotation==180: points=[(1-x,1-y) for x,y in points]
        elif self.rotation==270: points=[(y,1-x) for x,y in points]
        return [min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)]

class TableCell(StrictModel):
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    row_span: int = Field(default=1,ge=1)
    column_span: int = Field(default=1,ge=1)
    text: str
    header: bool = False

class DocumentBlock(StrictModel):
    id: str
    ordinal: int = Field(ge=0)
    page: int = Field(ge=1)
    type: str
    text: str
    bbox: list[float] | None = None
    coordinate_space: Literal['normalized_1000','pixels'] | None = None
    locator: str
    raw: dict = Field(default_factory=dict)
    table_rows: list[list[str]] | None = None
    table_cells: list[TableCell] | None = None
    vendor_source_ref: str | None = None
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    @model_validator(mode='after')
    def frame(self):
        if self.bbox is not None:
            if self.coordinate_space!='normalized_1000': raise ValueError('Document display rectangles must declare normalized_1000')
            CoordinateFrame(units='normalized_1000',width=1000,height=1000).normalized(self.bbox)
        return self

class ParserCapabilities(StrictModel):
    id: str
    name: str
    version: str
    available: bool
    formats: list[str]
    page_ranges: bool
    ocr: bool = False
    description: str

class EvidenceDocument(StrictModel):
    schema_version: Literal['evidence-document.v1'] = 'evidence-document.v1'
    case_id: str
    evidence_id: str
    parse_run_id: str
    snapshot_id: str
    source_sha256: str
    parser: str
    profile_digest: str
    page_kind: Literal['physical_page','logical_unit','image']
    pages: int
    blocks: list[DocumentBlock]

class ParseArtifact(StrictModel):
    filename: str
    sha256: str
    size: int = Field(ge=0)
    source_sha256: str
    parser_revision: str
    profile_digest: str
    start: int = Field(ge=0)
    count: int = Field(ge=1)
    output_schema_version: str

class ParseRun(StrictModel):
    id: str
    evidence_id: str
    source_sha256: str
    profile_digest: str
    parser: str
    status: Literal['pending','parsing','interrupted','partial','complete','failed']
    parsed_units: int = Field(ge=0)
    total_units: int | None
    artifacts: list[ParseArtifact] = Field(default_factory=list)
    quality_status: Literal['unreviewed'] = 'unreviewed'

class ParseJobView(StrictModel):
    id: str
    case_id: str
    document_id: str
    status: Literal['queued','running','partial','succeeded','failed','cancelled']
    pages: int
    all_pages: bool
    actor_id: str
    created_at: float
    updated_at: float
    parsed_pages: int
    total_pages: int | None
    cancel_requested: bool
    error: dict[str,str] | None = None
