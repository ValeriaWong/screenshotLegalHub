from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    data_dir: Path = ROOT / 'data'
    host: str = '0.0.0.0'
    session_hours: int = 8
    session_secure_cookie: bool = False
    trusted_origins: list[str] = ['http://127.0.0.1:18431','http://localhost:18431','http://127.0.0.1:18430','http://localhost:18430']
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl"] = "starttls"
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    smtp_timeout_seconds: float = Field(default=15, gt=0, le=120)
    max_upload_bytes: int = 20 * 1024 * 1024
    max_batch_files: int = 50
    max_batch_bytes: int = 100 * 1024 * 1024
    allowed_mime_types: list[str] = ['image/png', 'image/jpeg', 'image/webp', 'application/pdf', 'text/plain']
    enable_real_model: bool = False
    allow_external_egress: bool = False
    model_base_url: str = ''
    model_request_timeout_seconds: int = 90
    model_request_total_timeout_seconds: int | None = None
    model_max_output_tokens: int | None = None
    model_name: str = ''
    model_api_key: str = ''
    auto_approve_gates: bool = False
    skill_allowlist: list[str] = []
    allowed_permissions: list[str] = ['retrieval']

    @property
    def database_url(self):
        return 'sqlite:///' + (self.data_dir / 'screenshotlegal.sqlite3').as_posix()
