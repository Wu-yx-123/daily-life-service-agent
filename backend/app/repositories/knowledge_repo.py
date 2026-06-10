# 作用：封装知识库文档的检索和种子写入。
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import KnowledgeDocument


class KnowledgeRepository:
    """知识库仓储。

    Phase 3 先用关键词检索实现最小可运行知识库，后续可替换为 ChromaDB/Elasticsearch。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **data) -> KnowledgeDocument:
        """创建知识文档。"""
        document = KnowledgeDocument(**data)
        self.db.add(document)
        await self.db.flush()
        return document

    async def search(self, *, query: str, category: str | None = None, limit: int = 3) -> list[KnowledgeDocument]:
        """按标题、正文和分类做轻量关键词检索。"""
        words = [word for word in query.replace("，", " ").replace("。", " ").split() if word]
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.status == "active")
        if category:
            stmt = stmt.where(KnowledgeDocument.category == category)
        if words:
            conditions = []
            for word in words:
                pattern = f"%{word}%"
                conditions.append(KnowledgeDocument.title.ilike(pattern))
                conditions.append(KnowledgeDocument.content.ilike(pattern))
            stmt = stmt.where(or_(*conditions))
        return list((await self.db.scalars(stmt.limit(limit))).all())
