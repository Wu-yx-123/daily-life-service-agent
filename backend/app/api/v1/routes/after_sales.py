# 作用：提供售后工单查询接口，支撑 Phase 3 售后页面和运营查看。
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.after_sales_repo import AfterSalesRepository
from app.schemas.agent import AfterSalesTicketResponse

router = APIRouter(prefix="/after-sales", tags=["after-sales"])


def _to_response(ticket) -> AfterSalesTicketResponse:
    """把 ORM 售后工单转换成 API 响应。"""
    return AfterSalesTicketResponse(
        id=str(ticket.id),
        trace_id=ticket.trace_id,
        session_id=ticket.session_id,
        user_id=ticket.user_id,
        ticket_type=ticket.ticket_type,
        status=ticket.status,
        priority=ticket.priority,
        summary=ticket.summary,
        suggested_action=ticket.suggested_action,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.get("", response_model=list[AfterSalesTicketResponse])
async def list_after_sales(status: str | None = None, db: AsyncSession = Depends(get_db)):
    """查询售后工单。"""
    tickets = await AfterSalesRepository(db).list(status=status)
    return [_to_response(ticket) for ticket in tickets]
