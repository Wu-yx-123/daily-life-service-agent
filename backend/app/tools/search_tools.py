# 作用：知识库搜索和服务搜索工具，供 KnowledgeAgent 和 MatchAgent 调用。
# 检索链：MCP RAG Server (agentic RAG) → SQL 关键词 → 兜底文案
import logging

from app.repositories.knowledge_repo import KnowledgeRepository

logger = logging.getLogger(__name__)


async def search_knowledge(
    *,
    knowledge_repo: KnowledgeRepository,
    query: str,
    category: str | None = None,
    top_k: int = 5,
    **kwargs,
) -> dict:
    """搜索知识库文档，按优先级逐层回退。

    检索链（任一命中即返回）：
      1. 外部 MCP RAG Server（agentic RAG，支持 query rewrite / rerank）
      2. PostgreSQL ILIKE 关键词匹配
      3. 兜底文案

    返回：
      {"answer": str, "hits": [...], "source": "mcp_rag"|"sql"|"fallback"}
    """
    # ── 第 1 层：外部 MCP RAG Server ──
    try:
        from app.core.mcp_rag_client import get_mcp_rag_client
        from app.core.config import get_settings

        client = get_mcp_rag_client()
        if client.available or await client.initialize():
            collection = category or get_settings().mcp_rag_collection
            result = await client.search(
                query=query,
                collection=collection,
                top_k=top_k,
            )
            if result.get("hits"):
                logger.info("search_knowledge → MCP RAG (%d hits)", len(result["hits"]))
                return result
    except Exception as exc:
        logger.warning("MCP RAG 检索失败，回退 SQL：%s", exc)

    # ── 第 2 层：PostgreSQL 关键词匹配 ──
    docs = await knowledge_repo.search(query=query, category=category)
    hits = [
        {
            "id": str(doc.id),
            "title": doc.title,
            "category": doc.category,
            "content": doc.content,
            "score": 1.0,
        }
        for doc in docs
    ]
    source = "sql" if hits else "fallback"
    if hits:
        logger.info("search_knowledge → SQL (%d hits)", len(hits))

    # ── 拼合回答 ──
    if not hits:
        answer = "暂未找到相关门店规则或售后政策，请转人工确认。"
    else:
        top = hits[:2]
        answer = "；".join(f"{h['title']}：{h['content']}" for h in top)
    return {"answer": answer, "hits": hits, "source": source}


async def search_services_by_keyword(
    *,
    knowledge_repo: KnowledgeRepository,
    query: str,
    **kwargs,
) -> list[dict]:
    """关键词搜索服务项目。

    用于非结构化服务发现，例如用户输入"放松一下"时匹配到"全身放松"服务。
    """
    from sqlalchemy import or_, select
    from app.models.business import Service

    db = knowledge_repo.db
    stmt = select(Service).where(Service.status == "active")
    words = [w for w in query.replace("，", " ").replace("。", " ").split() if w]
    if words:
        conditions = []
        for word in words:
            pattern = f"%{word}%"
            conditions.append(Service.name.ilike(pattern))
            conditions.append(Service.description.ilike(pattern))
            conditions.append(Service.category.ilike(pattern))
        stmt = stmt.where(or_(*conditions))
    services = list((await db.scalars(stmt.limit(10))).all())
    return [
        {"id": str(s.id), "store_id": str(s.store_id), "name": s.name,
         "category": s.category, "duration_minutes": s.duration_minutes,
         "base_price": str(s.base_price), "description": s.description, "tags": s.tags}
        for s in services
    ]


async def list_knowledge_collections(**kwargs) -> list[dict]:
    """列出 MCP RAG Server 上所有知识库 collection。"""
    try:
        from app.core.mcp_rag_client import get_mcp_rag_client
        client = get_mcp_rag_client()
        if client.available or await client.initialize():
            return await client.list_collections(include_stats=True)
    except Exception:
        pass
    return []


async def get_knowledge_document(*, doc_id: str, collection: str | None = None, **kwargs) -> dict:
    """获取 MCP RAG Server 上指定文档的摘要。"""
    try:
        from app.core.mcp_rag_client import get_mcp_rag_client
        client = get_mcp_rag_client()
        if client.available or await client.initialize():
            return await client.get_document_summary(doc_id=doc_id, collection=collection)
    except Exception:
        pass
    return {}
