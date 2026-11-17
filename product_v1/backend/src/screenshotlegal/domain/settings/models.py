from typing import Literal
from pydantic import Field, SecretStr
from screenshotlegal.domain.common.models import StrictModel
from screenshotlegal.domain.evidence.models import EvidenceItem


class LocalUser(StrictModel):
    display_name: str = Field(default='本地用户', min_length=1, max_length=100)
    organization: str = Field(default='', max_length=200)


class ModelUsageSettings(StrictModel):
    request_timeout_seconds: int = Field(default=90, ge=1, le=3600)
    request_total_timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    max_output_tokens: int | None = Field(default=None, ge=1)
    input_token_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_token_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    price_currency: Literal["CNY", "USD"] = "CNY"


class ModelConfiguration(ModelUsageSettings):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=2048)
    model_name: str = Field(min_length=1, max_length=200)
    api_key: SecretStr | None = None
    supports_vision: bool = True
    allow_external_egress: bool = False


class ModelConnectivity(StrictModel):
    success: bool
    checked_at: str
    latency_ms: int = Field(ge=0)


class ModelView(ModelUsageSettings):
    id: str
    name: str
    base_url: str
    model_name: str
    supports_vision: bool
    allow_external_egress: bool
    has_api_key: bool
    is_default: bool
    connectivity: dict[Literal["text", "image"], ModelConnectivity] = Field(default_factory=dict)


class ModelSelection(StrictModel):
    model_id: str | None = None


class ConnectivityImage(StrictModel):
    case_id: str
    evidence_id: str
    case_title: str
    filename: str


class ConnectivityRequest(StrictModel):
    mode: Literal["text", "image"] = "text"
    case_id: str | None = None
    evidence_id: str | None = None


class ConnectivityResult(StrictModel):
    success: bool
    latency_ms: int
    message: str
    mode: Literal["text", "image"] = "text"
    case_id: str | None = None
    evidence_id: str | None = None


class UploadResult(StrictModel):
    index: int
    filename: str
    status: str
    evidence: EvidenceItem | None = None
    error: str | None = None


class BatchUploadResult(StrictModel):
    results: list[UploadResult]
    uploaded: int
    duplicates: int
    failed: int
