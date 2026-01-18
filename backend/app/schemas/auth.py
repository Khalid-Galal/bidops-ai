"""Authentication schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.base import UserRole


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(min_length=6)


class LoginResponse(BaseModel):
    """Login response with tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: "UserResponse"


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class TokenRefreshResponse(BaseModel):
    """Token refresh response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    """User creation schema."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = None
    role: UserRole = UserRole.VIEWER
    organization_id: int


class UserUpdate(BaseModel):
    """User update schema."""

    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    email: str
    full_name: str
    phone: Optional[str]
    avatar_url: Optional[str]
    role: UserRole
    organization_id: int
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str = Field(min_length=8)


class PasswordResetRequest(BaseModel):
    """Password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""

    token: str
    new_password: str = Field(min_length=8)
