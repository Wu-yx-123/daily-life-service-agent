# 作用：KnowledgeAgent 负责查询服务说明、门店规则和售后政策。
# 返回结构化证据链（evidence_chunks），供 CustomerServiceAgent 和售后工单使用。
import logging

from app.repositories.knowledge_repo import KnowledgeRepository
from app.schemas.agent import EvidenceChunk, KnowledgeAnswer

logger = logging.getLogger(__name__)


class KnowledgeAgent:
    """知识库 Agent——返回结构化证据链。

    检索链：MCP RAG Server（agentic RAG）→ SQL 关键词 → 兜底提示。
    evidence 字段包含可追溯的 source_file / doc_type / chunk_id / score / text，
    最终存入售后工单的 policy_basis JSONB 字段。
    """

    name = "KnowledgeAgent"

    def __init__(self, repo: KnowledgeRepository):
        self.repo = repo

    async def run(self, *, query: str, category: str | None = None) -> KnowledgeAnswer:
        from app.tools.search_tools import search_knowledge

        result = await search_knowledge(knowledge_repo=self.repo, query=query, category=category)

        evidence = [
            EvidenceChunk(
                source_file=e.get("source_file", ""),
                doc_type=e.get("doc_type", ""),
                chunk_id=e.get("chunk_id", ""),
                score=e.get("score", 0.0),
                text=e.get("text", e.get("content", "")),
            )
            for e in result.get("evidence", [])
        ]
        return KnowledgeAnswer(
            query=query,
            answer=result["answer"],
            evidence=evidence,
            hits=result.get("hits", []),
            source=result.get("source", "fallback"),
        )

    async def list_collections(self) -> list[dict]:
        """列出 MCP RAG Server 所有知识库 collection。"""
        from app.tools.search_tools import list_knowledge_collections
        return await list_knowledge_collections()

    async def get_document(self, *, doc_id: str, collection: str | None = None) -> dict:
        """获取指定文档的摘要信息。"""
        from app.tools.search_tools import get_knowledge_document
        return await get_knowledge_document(doc_id=doc_id, collection=collection)
