"""认证相关请求/响应模型。"""
from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64, description="用户名")
    password: str = Field(min_length=6, max_length=64, description="密码")
    role: str = Field(default="student", pattern="^(student|teacher)$", description="角色")
    full_name: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=128)
    grade: Optional[str] = Field(default=None, description="学生年级（下拉选择）")
    subject: Optional[str] = Field(default=None, description="教师学科（单选）")


class LoginRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = Field(default=None, pattern="^(admin|teacher|student)$", description="按角色限定登录（用户名可重复时用于区分）")


class RefreshRequest(BaseModel):
    refresh_token: str


class UserBrief(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    avatar: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserBrief