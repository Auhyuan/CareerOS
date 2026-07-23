from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """用户注册参数。"""

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_\-]+$")
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """清理用户名首尾空格并统一按原始大小写保存。"""
        return value.strip()


class UserLoginRequest(BaseModel):
    """用户登录参数。"""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenRefreshRequest(BaseModel):
    """刷新访问令牌参数。"""

    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    """退出登录参数，用于撤销当前刷新令牌。"""

    refresh_token: str = Field(min_length=20)


class UserResponse(BaseModel):
    """返回给前端的安全用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    username: str
    email: str | None
    status: str


class TokenPairResponse(BaseModel):
    """登录或刷新成功后返回的双令牌。"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse
