# 作用：知识库 API——全文检索 + collection 列表 + 文档摘要 + 商家手册上传入库。
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.knowledge_agent import KnowledgeAgent
from app.core.config import get_settings
from app.core.database import get_db
from app.core.mcp_rag_client import MCPRagError, get_mcp_rag_client
from app.repositories.knowledge_repo import KnowledgeRepository
from app.schemas.agent import KnowledgeAnswer, KnowledgeQueryRequest

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

ALLOWED_MANUAL_SUFFIXES = {".pdf", ".md", ".markdown"}
UPLOAD_DIR = Path(__file__).resolve().parents[4] / "uploads" / "store_manuals"


@router.post("/query", response_model=KnowledgeAnswer)
async def query_knowledge(payload: KnowledgeQueryRequest, db: AsyncSession = Depends(get_db)):
    """全文检索——查询服务说明、门店规则和售后政策。"""
    return await KnowledgeAgent(KnowledgeRepository(db)).run(query=payload.query, category=payload.category)


@router.get("/collections")
async def list_collections(db: AsyncSession = Depends(get_db)):
    """列出 MCP RAG Server 所有知识库 collection。"""
    return await KnowledgeAgent(KnowledgeRepository(db)).list_collections()


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, collection: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    """获取指定文档的摘要与元数据。"""
    return await KnowledgeAgent(KnowledgeRepository(db)).get_document(doc_id=doc_id, collection=collection)


@router.post("/manuals/upload")
async def upload_store_manual(
    file: UploadFile = File(...),
    collection: str = Form("massage_shop_rules"),
    force: bool = Form(False),
):
    """商家上传门店业务手册，并通过 MCP RAG Server 触发入库。"""
    original_name = file.filename or "store_manual.pdf"
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_MANUAL_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 PDF / Markdown 手册文件")

    safe_stem = re.sub(r"[^0-9A-Za-z._-]+", "_", Path(original_name).stem).strip("._") or "store_manual"
    target_dir = UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid4().hex}_{safe_stem}{suffix}"

    size = 0
    try:
        with target_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                out.write(chunk)
    finally:
        await file.close()

    if size == 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        client = get_mcp_rag_client()
        result = await client.ingest_document(
            file_path=str(target_path.resolve()),
            collection=collection or get_settings().mcp_rag_collection,
            force=force,
        )
    except MCPRagError as exc:
        raise HTTPException(status_code=502, detail=f"MCP RAG Server 入库失败: {exc}") from exc

    if result.get("is_error") or result.get("success") is False:
        raise HTTPException(status_code=502, detail=result.get("error") or result.get("raw") or "MCP 入库失败")

    return {
        "success": True,
        "file_name": original_name,
        "stored_path": str(target_path.resolve()),
        "collection": result.get("collection", collection),
        "doc_id": result.get("doc_id"),
        "chunk_count": result.get("chunk_count", 0),
        "image_count": result.get("image_count", 0),
        "skipped": bool(result.get("skipped", False)),
        "message": "手册已存在，已跳过重复入库。" if result.get("skipped") else "手册已上传并完成入库。",
    }
