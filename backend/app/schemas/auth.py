from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: Optional[str] = None
    device_fingerprint: Optional[str] = None

    @field_validator('password')
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('Password must be at most 72 UTF-8 bytes')
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=8192)
    csrf_token: Optional[str] = Field(default=None, max_length=128)
    device_fingerprint: Optional[str] = Field(default=None, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]



class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class GoogleStartRequest(BaseModel):
    device_fingerprint: Optional[str] = Field(default=None, max_length=128)
