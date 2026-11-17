from typing import Literal
from pydantic import Field, SecretStr
from screenshotlegal.domain.common.models import StrictModel


class LoginRequest(StrictModel):
    username: str = Field(min_length=3, max_length=64, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]+$')
    password: SecretStr


class CreateUserRequest(LoginRequest):
    display_name: str = Field(min_length=1, max_length=100)
    role: Literal['admin', 'member'] = 'member'


class UserView(StrictModel):
    id: str
    username: str
    display_name: str
    organization: str = ''
    role: Literal['admin', 'member']
    enabled: bool = True


class UpdateUserRequest(StrictModel):
    role: Literal['admin', 'member']
    enabled: bool


class PasswordRequest(StrictModel):
    current_password: SecretStr
    new_password: SecretStr


class ShareRequest(StrictModel):
    username: str
    role: Literal['viewer', 'editor', 'remove']
