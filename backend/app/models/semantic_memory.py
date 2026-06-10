# 作用：定义用户语义长期记忆模型，使用 pgvector 保存非结构化记忆片段。
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.core.database import Base
from app.core.embeddings import EMBEDDING_DIMENSION
from app.core.types import GUID


class Vector(UserDefinedType):
    """SQLAlchemy 自定义 pgvector 类型。

    项目没有额外引入 pgvector Python 包，因此用轻量 UserDefinedType 让 create_all 能生成 vector(1536)。
    实际写入和相似度查询由仓储层用 SQL 完成。
    """

    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        return f"vector({EMBEDDING_DIMENSION})"


class UserMemoryChunk(Base):
    """用户语义长期记忆表。

    和 user_preferences 的结构化偏好不同，这里保存自然语言摘要，适合记录身体状态、体验反馈、
    特殊注意事项等不容易拆成固定字段的信息。
    """

    __tablename__ = "user_memory_chunks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(), nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="booking_confirmed", nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSON)
    importance: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.60"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
