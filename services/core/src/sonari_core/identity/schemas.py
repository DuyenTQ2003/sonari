"""Request and response bodies of /v1/auth. JSON fields are camelCase."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RegisterRequest(CamelModel):
    email: EmailStr
    # Length only, as NIST SP 800-63B advises; the cap bounds what argon2 must hash.
    password: str = Field(min_length=8, max_length=128)
    turnstile_token: str = Field(min_length=1, max_length=2048)


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(CamelModel):
    id: str
    email: str


class AuthResponse(CamelModel):
    user: UserResponse
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
