from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.common.core.exceptions import BusinessException
from app.common.core.security import decode_token
from app.common.db.postgres import get_db_session
from app.server.auth.src.models.auth_models import UserModel
from app.server.auth.src.repository.auth_repository import AuthRepository


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db_session)],
) -> UserModel:
    """解析 Bearer Access Token，并返回当前启用用户。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise BusinessException(401, "请先登录")
    claims = decode_token(credentials.credentials, "access")
    user = AuthRepository.get_user_by_id(db, claims.user_id)
    if user is None or user.status != "active":
        raise BusinessException(401, "用户不存在或已停用")
    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]
