from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.db.postgres import get_db_session
from app.common.schemas.result import Result
from app.server.auth.src.dependencies import CurrentUser
from app.server.auth.src.schemas.auth_schemas import (
    LogoutRequest,
    TokenPairResponse,
    TokenRefreshRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.server.auth.src.service.auth_service import AuthService


router = APIRouter()
auth_service = AuthService()
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post("/register", response_model=Result[UserResponse], summary="注册用户")
def register(request: UserRegisterRequest, db: DbSession) -> Result[UserResponse]:
    """创建本地用户，密码只以 Argon2 哈希形式保存。"""
    return Result.success(auth_service.register(db, request), msg="注册成功")


@router.post("/login", response_model=Result[TokenPairResponse], summary="用户登录")
def login(request: UserLoginRequest, db: DbSession) -> Result[TokenPairResponse]:
    """验证账号密码并返回 Access Token 与 Refresh Token。"""
    return Result.success(auth_service.login(db, request), msg="登录成功")


@router.post("/refresh", response_model=Result[TokenPairResponse], summary="刷新登录令牌")
def refresh(request: TokenRefreshRequest, db: DbSession) -> Result[TokenPairResponse]:
    """轮换刷新令牌并签发新的双令牌。"""
    return Result.success(auth_service.refresh(db, request.refresh_token), msg="令牌刷新成功")


@router.post("/logout", response_model=Result[None], summary="退出登录")
def logout(request: LogoutRequest, current_user: CurrentUser, db: DbSession) -> Result[None]:
    """撤销当前用户提交的刷新令牌。"""
    auth_service.logout(db, current_user.user_id, request.refresh_token)
    return Result.success(msg="退出登录成功")


@router.post("/me", response_model=Result[UserResponse], summary="查询当前用户")
def get_me(current_user: CurrentUser) -> Result[UserResponse]:
    """根据 Access Token 返回当前用户信息。"""
    return Result.success(UserResponse.model_validate(current_user))
