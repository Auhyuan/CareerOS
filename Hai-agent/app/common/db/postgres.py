from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.common.config.settings import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的声明式基类。"""


DATABASE_URL = URL.create(
    "postgresql+psycopg",
    username=settings.postgres_user,
    password=settings.postgres_password,
    host=settings.postgres_host,
    port=settings.postgres_port,
    database=settings.postgres_database,
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.postgres_pool_size,
    max_overflow=settings.postgres_max_overflow,
    connect_args={"connect_timeout": settings.postgres_connect_timeout},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def check_postgres_health() -> None:
    """在服务启动时检查 PostgreSQL 连接和 hai Schema 是否存在。"""
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        schema_exists = db.execute(
            text("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema_name)"),
            {"schema_name": settings.postgres_schema},
        ).scalar_one()
        if not schema_exists:
            raise RuntimeError(
                f"PostgreSQL Schema {settings.postgres_schema!r} 不存在，请先执行 sql/001_initial_schema.sql"
            )


def get_db_session() -> Generator[Session, None, None]:
    """为 FastAPI 请求提供独立数据库会话，并在请求结束后关闭连接。"""
    with SessionLocal() as db:
        yield db


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """为非 FastAPI 调用提供自动提交和回滚的数据库事务。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
