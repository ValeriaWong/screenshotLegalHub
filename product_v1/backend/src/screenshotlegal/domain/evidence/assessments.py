from typing import Literal
from pydantic import Field
from screenshotlegal.domain.common.models import StrictModel

class Party(StrictModel):
    id: str
    name: str
    identity_status: Literal['unreviewed','verified','disputed'] = 'unreviewed'
    source_refs: list[str] = []

class Reconciliation(StrictModel):
    id: str
    case_id: str
    source_ref_ids: list[str] = Field(min_length=2)
    relation: Literal['same_message','overlap','different','unresolved']
    rationale: str
    review_status: Literal['unreviewed','verified','rejected'] = 'unreviewed'

class LawyerAssessment(StrictModel):
    id: str
    case_id: str
    analysis_run_id: str
    target_id: str
    reviewed_output_digest: str
    action: Literal['verified','edited','rejected','deferred']
    text: str = ''
    reviewer: str
    created_at: str
