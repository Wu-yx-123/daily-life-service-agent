# 作用：配置 SQLAlchemy 异步 PostgreSQL 数据库连接和 FastAPI Session 依赖。
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的基类。"""
    pass


engine = create_async_engine(get_settings().database_url, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def create_test_engine(database_url: str = ""):
    """为测试创建独立引擎（使用独立的 test 数据库）。"""
    url = database_url or get_settings().test_database_url
    return create_async_engine(url, future=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 数据库依赖：每个请求独立创建一个异步 Session。"""
    async with AsyncSessionLocal() as session:
        yield session

