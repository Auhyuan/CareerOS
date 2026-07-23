import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.common.config.settings import get_settings
from app.common.core.exceptions import BusinessException


password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("hai-agent-dummy-password")


@dataclass(frozen=True)
class TokenClaims:
    """保存 JWT 解码后经过校验的核心声明。"""

    user_id: UUID
    token_type: str
    token_id: UUID
    expires_at: datetime


def hash_password(password: str) -> str:
    """使用 Argon2 对用户密码进行不可逆哈希。"""
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    """验证明文密码是否与数据库中的 Argon2 哈希一致。"""
    return password_hash.verify(password, encoded_hash)


def verify_dummy_password(password: str) -> None:
    """用户不存在时仍执行一次密码验证，降低用户名枚举的时间差。"""
    password_hash.verify(password, DUMMY_PASSWORD_HASH)


def create_token(user_id: UUID, token_type: str, expires_delta: timedelta) -> tuple[str, UUID, datetime]:
    """创建带用户、类型、唯一 ID 和过期时间的 JWT。"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    token_id = uuid4()
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": str(token_id),
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, token_id, expires_at


def create_access_token(user_id: UUID) -> tuple[str, UUID, datetime]:
    """创建短期访问令牌。"""
    settings = get_settings()
    return create_token(user_id, "access", timedelta(minutes=settings.jwt_access_token_minutes))


def create_refresh_token(user_id: UUID) -> tuple[str, UUID, datetime]:
    """创建用于换取新令牌的长期刷新令牌。"""
    settings = get_settings()
    return create_token(user_id, "refresh", timedelta(days=settings.jwt_refresh_token_days))


def decode_token(token: str, expected_type: str) -> TokenClaims:
    """验证 JWT 签名、签发方、受众、过期时间和令牌类型。"""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        token_type = str(payload.get("type", ""))
        if token_type != expected_type:
            raise BusinessException(401, "令牌类型不正确")
        return TokenClaims(
            user_id=UUID(str(payload["sub"])),
            token_type=token_type,
            token_id=UUID(str(payload["jti"])),
            expires_at=datetime.fromtimestamp(float(payload["exp"]), tz=timezone.utc),
        )
    except BusinessException:
        raise
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise BusinessException(401, "登录状态无效或已过期") from error


def hash_token(token: str) -> str:
    """对刷新令牌做 SHA-256 摘要，数据库不保存令牌明文。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
