from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.server.auth.src.models.auth_models import RefreshTokenModel, UserModel


class AuthRepository:
    """封装用户和刷新令牌的数据库读写。"""

    @staticmethod
    def get_user_by_id(db: Session, user_id: UUID) -> UserModel | None:
        """根据 user_id 查询用户。"""
        return db.scalar(select(UserModel).where(UserModel.user_id == user_id))

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> UserModel | None:
        """使用不区分大小写的用户名查询用户。"""
        return db.scalar(select(UserModel).where(UserModel.username.ilike(username.strip())))

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> UserModel | None:
        """使用不区分大小写的邮箱查询用户。"""
        return db.scalar(select(UserModel).where(UserModel.email.ilike(email.strip())))

    @staticmethod
    def add_user(db: Session, user: UserModel) -> UserModel:
        """把新用户加入当前事务。"""
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def add_refresh_token(db: Session, token: RefreshTokenModel) -> None:
        """保存刷新令牌摘要。"""
        db.add(token)
        db.flush()

    @staticmethod
    def get_refresh_token_for_update(db: Session, token_id: UUID) -> RefreshTokenModel | None:
        """锁定刷新令牌记录，避免并发刷新产生多个有效令牌。"""
        statement = select(RefreshTokenModel).where(RefreshTokenModel.token_id == token_id).with_for_update()
        return db.scalar(statement)

    @staticmethod
    def revoke_refresh_token(token: RefreshTokenModel, revoked_at: datetime) -> None:
        """把刷新令牌标记为已撤销。"""
        token.revoked_at = revoked_at
