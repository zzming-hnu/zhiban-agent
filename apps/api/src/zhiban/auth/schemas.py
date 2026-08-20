"""Auth request/response Pydantic schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=100)


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserView(ApiModel):
    id: str
    email: str
    display_name: str


class SessionView(ApiModel):
    id: str
    created_at: str
    last_seen_at: str
    expires_at: str
    user_agent_hash: str | None = None


class AuthResponse(ApiModel):
    user: UserView
    session: SessionView
