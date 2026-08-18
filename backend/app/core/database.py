"""MySQL 异步连接（SQLAlchemy 2.0 + aiomysql）。"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖：为每个请求提供独立数据库会话。"""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """初始化数据表（幂等）。正式环境建议使用 scripts/init_mysql.sql。"""
    from app import models  # noqa: F401  确保模型已注册到 Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)