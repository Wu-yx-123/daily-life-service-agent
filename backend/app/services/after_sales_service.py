# 作用：封装售后工单创建逻辑，保存 RAG 证据链到 policy_basis。
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.knowledge_agent import KnowledgeAgent
from app.repositories.after_sales_repo import AfterSalesRepository
from app.repositories.knowledge_repo import KnowledgeRepository
from app.schemas.agent import CustomerServiceOutput

POLICY_QUERY_BY_TICKET_TYPE = {
    "cancel_order": "取消 预约 规则",
    "reschedule_order": "改期 处理 规则",
    "refund_request": "退款 处理 规则",
    "complaint": "投诉 处理 规则",
}


class AfterSalesService:
    """售后服务——工单创建时自动查询知识库并保存可追溯的政策依据。"""

    def __init__(self, db: AsyncSession, repo: AfterSalesRepository, knowledge_agent: KnowledgeAgent | None = None):
        self.db = db
        self.repo = repo
        self.knowledge_agent = knowledge_agent or KnowledgeAgent(KnowledgeRepository(db))

    async def create_ticket(
        self, *, trace_id: str, session_id: str | None, user_id: str,
        output: CustomerServiceOutput, policy_basis: list[dict] | None = None,
    ):
        """创建售后工单，附带 RAG 证据链写入 policy_basis JSONB。

        Args:
            policy_basis: KnowledgeAgent 返回的 evidence 列表，
                         每项含 source_file/doc_type/chunk_id/score/text。
        """
        # 如果上游没有传 policy_basis，这里自己查一次知识库
        if not policy_basis:
            policy_query = POLICY_QUERY_BY_TICKET_TYPE.get(output.ticket_type, output.ticket_type)
            kb_result = await self.knowledge_agent.run(query=policy_query)
            policy_basis = [e.model_dump() for e in kb_result.evidence]

        suggested_action = output.suggested_action
        if policy_basis:
            top = policy_basis[0]
            suggested_action = (
                f"{suggested_action} 政策依据：{top.get('source_file', '')} "
                f"(相关度 {top.get('score', 0):.0%})"
            )

        ticket = await self.repo.create(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            ticket_type=output.ticket_type,
            status="open",
            priority=output.priority,
            summary=output.summary,
            suggested_action=suggested_action,
            policy_basis=policy_basis if policy_basis else None,
        )
        await self.db.commit()
        return ticket
