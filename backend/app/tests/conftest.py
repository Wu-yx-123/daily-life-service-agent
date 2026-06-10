# 作用：为后端测试提供 PostgreSQL 数据库、内存时间锁和 FastAPI 测试客户端。
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.api.deps import get_time_lock_store
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.redis import InMemoryRedis, TimeLockStore
from app.main import create_app
from app.services.seed_service import ensure_demo_data


@pytest.fixture
async def db_session():
    """每个测试独立 PostgreSQL 引擎 + Session，测试结束销毁。"""
    url = get_settings().test_database_url
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        # pgvector 表依赖 vector 扩展；测试库每次重建后都要先启用扩展再 create_all。
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        await ensure_demo_data(session)
        await session.commit()
        yield session
        await session.rollback()
    # 清空表，下次测试重新 create_all（幂等）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def memory_lock_store():
    """测试用内存时间锁。"""
    return TimeLockStore(InMemoryRedis(), ttl_seconds=600)


@pytest.fixture
async def client(db_session, memory_lock_store):
    """带依赖覆盖的 FastAPI 测试客户端。"""
    app = create_app()

    async def override_db():
        yield db_session

    async def override_lock_store():
        yield memory_lock_store

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_time_lock_store] = override_lock_store
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
