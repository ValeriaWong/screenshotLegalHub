from typing import Literal
from pydantic import Field
from screenshotlegal.domain.common.models import StrictModel

class ParseOptions(StrictModel):
    parser: Literal["auto","mineru","docling","paddle"] = "auto"
    # This is an actual native-text parsing option, not a claimed OCR model change.
    text_chunk_chars: int = Field(default=1600,ge=200,le=8000)

class ReadRange(StrictModel):
    across_blocks: bool = False
    block_id: str
    start: int = Field(default=0,ge=0)
    max_chars: int = Field(default=3000,ge=1,le=30000)
