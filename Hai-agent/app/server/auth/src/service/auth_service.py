from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.config.settings import get_settings
from app.common.core.exceptions import BusinessException
from app.common.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_dummy_password,
    verify_password,
)
from app.server.auth.src.models.auth_models import RefreshTokenModel, UserModel
from app.server.auth.src.repository.auth_repository import AuthRepository
from app.server.auth.src.schemas.auth_schemas import (
    TokenPairResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)


class AuthService:
    """实现用户注册、登录、令牌轮换和退出登录。"""

    def __init__(self, repository: AuthRepository | None = None):
        """初始化认证服务及其数据仓储。"""
        self.repository = repository or AuthRepository()

    def register(self, db: Session, request: UserRegisterRequest) -> UserResponse:
        """注册用户，并确保用户名和邮箱不重复。"""
        if self.repository.get_user_by_username(db, request.username):
            raise BusinessException(409, "用户名已存在")
        if request.email and self.repository.get_user_by_email(db, str(request.email)):
            raise BusinessException(409, "邮箱已存在")

        user = UserModel(
            username=request.username,
            email=str(request.email).lower() if request.email else None,
            password_hash=hash_password(request.password),
        )
        try:
            self.repository.add_user(db, user)
            db.commit()
        except IntegrityError as error:
            db.rollback()
            raise BusinessException(409, "用户名或邮箱已存在") from error
        return UserResponse.model_validate(user)

    def login(self, db: Session, request: UserLoginRequest) -> TokenPairResponse:
        """验证用户名和密码，签发 access/refresh 双令牌。"""
        user = self.repository.get_user_by_username(db, request.username)
        if user is None:
            verify_dummy_password(request.password)
            raise BusinessException(401, "用户名或密码错误")
        if not verify_password(request.password, user.password_hash):
            raise BusinessException(401, "用户名或密码错误")
        if user.status != "active":
            raise BusinessException(403, "当前用户已停用")

        user.last_login_at = datetime.now(timezone.utc)
        response = self._issue_token_pair(db, user)
        db.commit()
        return response

    def refresh(self, db: Session, raw_refresh_token: str) -> TokenPairResponse:
        """验证并轮换刷新令牌，旧刷新令牌立即失效。"""
        claims = decode_token(raw_refresh_token, "refresh")
        stored_token = self.repository.get_refresh_token_for_update(db, claims.token_id)
        now = datetime.now(timezone.utc)
        if (
            stored_token is None
            or stored_token.user_id != claims.user_id
            or stored_token.revoked_at is not None
            or stored_token.expires_at <= now
            or stored_token.token_hash != hash_token(raw_refresh_token)
        ):
            db.rollback()
            raise BusinessException(401, "刷新令牌无效或已使用")

        user = self.repository.get_user_by_id(db, claims.user_id)
        if user is None or user.status != "active":
            db.rollback()
            raise BusinessException(401, "用户不存在或已停用")

        self.repository.revoke_refresh_token(stored_token, now)
        response = self._issue_token_pair(db, user)
        db.commit()
        return response

    def logout(self, db: Session, user_id: UUID, raw_refresh_token: str) -> None:
        """撤销属于当前用户的刷新令牌，使其不能再次换取访问令牌。"""
        claims = decode_token(raw_refresh_token, "refresh")
        if claims.user_id != user_id:
            raise BusinessException(403, "不能撤销其他用户的登录会话")
        stored_token = self.repository.get_refresh_token_for_update(db, claims.token_id)
        if stored_token and stored_token.revoked_at is None:
            self.repository.revoke_refresh_token(stored_token, datetime.now(timezone.utc))
            db.commit()

    def _issue_token_pair(self, db: Session, user: UserModel) -> TokenPairResponse:
        """签发双令牌，并只把刷新令牌摘要写入数据库。"""
        settings = get_settings()
        access_token, _, _ = create_access_token(user.user_id)
        refresh_token, refresh_token_id, refresh_expires_at = create_refresh_token(user.user_id)
        self.repository.add_refresh_token(
            db,
            RefreshTokenModel(
                token_id=refresh_token_id,
                user_id=user.user_id,
                token_hash=hash_token(refresh_token),
                expires_at=refresh_expires_at,
            ),
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_minutes * 60,
            user=UserResponse.model_validate(user),
        )
