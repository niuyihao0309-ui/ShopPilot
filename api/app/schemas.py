from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    status: str
    permissions: dict[str, bool]
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuthTokenRead(BaseModel):
    access_token: str
    token_type: str
    user: UserRead