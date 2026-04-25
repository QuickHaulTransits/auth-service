from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=20)
    password: str = Field(min_length=8, max_length=64)
    otp: str = Field(min_length=6, max_length=6)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 71:
            raise ValueError("Password is too long (max 71 bytes)")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        if not any(c in "@$!%*?&" for c in v):
            raise ValueError("Password must contain at least one special character (@$!%*?&)")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 71:
            raise ValueError("Password is too long (max 71 bytes)")
        return v


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: EmailStr


class SendOtpRequest(BaseModel):
    email: EmailStr
