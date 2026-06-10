#!/usr/bin/env python
"""将 PDF 导入 MCP RAG Server 并验证查询。

用法：
    python scripts/import_pdf_to_mcp_rag.py "../按摩店门规业务手册_约2万字 (1).pdf"
    python scripts/import_pdf_to_mcp_rag.py "../按摩店门规业务手册_约2万字 (1).pdf" --extract-only
    python scripts/import_pdf_to_mcp_rag.py "../按摩店门规业务手册_约2万字 (1).pdf" --tool ingest_document --execute

默认会先 dry-run，列出 MCP tools 和将调用的入库参数；加 --execute 才真正调用入库工具。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
import pdfplumber

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import get_settings

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

INGEST_KEYWORDS = ("ingest", "import", "upload", "add", "index", "create", "upsert")
DOC_KEYWORDS = ("document", "doc", "pdf", "file", "knowledge")
EXCLUDE_TOOL_PREFIXES = ("query", "search", "list", "get")


class MCPClient:
    """轻量 MCP Streamable HTTP 客户端，供入库脚本使用。"""

    def __init__(self, url: str, timeout: float = 60.0):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session_id: str | None = None
        self.request_id = 0
        self.http = httpx.AsyncClient(timeout=timeout, headers=HEADERS, trust_env=False)

    async def close(self) -> None:
        await self.http.aclose()

    async def initialize(self) -> None:
        result, headers = await self._post({
            "jsonrpc": JSONRPC_VERSION,
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "massageops-kb-importer", "version": "0.1.0"},
            },
        }, include_session=False)
        self.session_id = headers.get("mcp-session-id")
        await self._post({
            "jsonrpc": JSONRPC_VERSION,
            "method": "notifications/initialized",
            "params": {},
        })
        server = result.get("serverInfo", {}).get("name", "unknown")
        print(f"✅ MCP RAG Server 已连接: {server}")

    async def list_tools(self) -> list[dict[str, Any]]:
        result, _ = await self._post({"jsonrpc": JSONRPC_VERSION, "id": self._next_id(), "method": "tools/list", "params": {}})
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result, _ = await self._post({
            "jsonrpc": JSONRPC_VERSION,
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        return result

    async def _post(self, payload: dict[str, Any], *, include_session: bool = True) -> tuple[dict[str, Any], httpx.Headers]:
        headers = {"mcp-session-id": self.session_id} if include_session and self.session_id else {}
        resp = await self.http.post(self.url, json=payload, headers=headers)
        resp.raise_for_status()
        if not resp.content:
            return {}, resp.headers
        parsed = _parse_mcp_response(resp)
        if "error" in parsed:
            error = parsed["error"]
            raise RuntimeError(f"MCP error {error.get('code')}: {error.get('message')}")
        return parsed.get("result", parsed), resp.headers

    def _next_id(self) -> int:
        self.request_id += 1
        return self.request_id


def _parse_mcp_response(resp: httpx.Response) -> dict[str, Any]:
    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        return resp.json()
    for block in re.split(r"\n\n", resp.text.strip()):
        lines = [line[6:] for line in block.splitlines() if line.startswith("data: ")]
        if not lines:
            continue
        try:
            return json.loads("\n".join(lines))
        except json.JSONDecodeError:
            continue
    return {}


def extract_pdf_text(path: Path) -> tuple[str, int]:
    """提取 PDF 文本，供 MCP 工具需要 content/text 参数时使用。"""
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages), len(pdf.pages)


def choose_ingest_tool(tools: list[dict[str, Any]], explicit: str | None = None) -> dict[str, Any]:
    if explicit:
        for tool in tools:
            if tool.get("name") == explicit:
                return tool
        raise RuntimeError(f"未找到指定 MCP tool: {explicit}")

    scored: list[tuple[int, dict[str, Any]]] = []
    for tool in tools:
        name = str(tool.get("name", "")).lower()
        if name.startswith(EXCLUDE_TOOL_PREFIXES):
            continue
        score = sum(3 for kw in INGEST_KEYWORDS if kw in name) + sum(2 for kw in DOC_KEYWORDS if kw in name)
        if score:
            scored.append((score, tool))
    if not scored:
        names = ", ".join(str(tool.get("name")) for tool in tools)
        raise RuntimeError(f"未能自动识别入库工具。请使用 --tool 指定。当前 tools: {names}")
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def build_ingest_arguments(
    *,
    tool: dict[str, Any],
    pdf_path: Path,
    collection: str,
    doc_id: str,
    title: str,
    text: str,
    doc_type: str,
) -> dict[str, Any]:
    """根据 MCP tool 的 inputSchema 尽量自动填充入库参数。"""
    schema = tool.get("inputSchema") or {}
    props: dict[str, Any] = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    args: dict[str, Any] = {}

    for name, prop in props.items():
        lname = name.lower()
        if lname in {"collection", "collection_name", "index", "namespace"}:
            args[name] = collection
        elif lname in {"doc_id", "document_id", "id"}:
            args[name] = doc_id
        elif lname in {"title", "name"}:
            args[name] = title
        elif lname in {"file_path", "filepath", "path", "pdf_path", "source_path", "local_path"}:
            args[name] = str(pdf_path)
        elif lname in {"filename", "file_name"}:
            args[name] = pdf_path.name
        elif lname in {"content", "text", "document", "markdown", "raw_text", "text_content"}:
            args[name] = text
        elif lname in {"metadata", "meta"}:
            args[name] = {
                "source_file": pdf_path.name,
                "title": title,
                "doc_type": doc_type,
                "collection": collection,
            }
        elif lname in {"source", "source_file"}:
            args[name] = pdf_path.name
        elif lname in {"doc_type", "category"}:
            args[name] = doc_type
        elif name in required:
            default = prop.get("default") if isinstance(prop, dict) else None
            if default is not None:
                args[name] = default

    missing = [name for name in required if name not in args]
    if missing:
        raise RuntimeError(
            f"工具 {tool.get('name')} 仍缺少必填参数 {missing}。"
            "请用 --tool 指定正确工具，或根据 tools/list 输出调整脚本参数映射。"
        )
    return args


def print_tools(tools: list[dict[str, Any]]) -> None:
    print("\n可用 MCP tools:")
    for tool in tools:
        schema = tool.get("inputSchema") or {}
        required = schema.get("required") or []
        props = ", ".join((schema.get("properties") or {}).keys())
        print(f"- {tool.get('name')} required={required} props=[{props}]")


async def main(args: argparse.Namespace) -> int:
    settings = get_settings()
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        print(f"❌ PDF 不存在: {pdf_path}")
        return 1

    text, page_count = extract_pdf_text(pdf_path)
    print(f"📄 PDF: {pdf_path.name}")
    print(f"- 页数: {page_count}")
    print(f"- 提取文本: {len(text)} 字符")
    if args.extract_only:
        print("\n预览:")
        print(text[:1000])
        return 0

    server_url = args.server_url or settings.mcp_rag_server_url
    if not server_url:
        print("❌ 未配置 MCP RAG Server URL。请设置 MASSAGEOPS_MCP_RAG_SERVER_URL 或传 --server-url。")
        return 1

    client = MCPClient(server_url, timeout=args.timeout)
    try:
        await client.initialize()
        tools = await client.list_tools()
        print_tools(tools)
        tool = choose_ingest_tool(tools, explicit=args.tool)
        print(f"\n选中的入库工具: {tool.get('name')}")
        ingest_args = build_ingest_arguments(
            tool=tool,
            pdf_path=pdf_path,
            collection=args.collection or settings.mcp_rag_collection,
            doc_id=args.doc_id,
            title=args.title or pdf_path.stem,
            text=text,
            doc_type=args.doc_type,
        )
        safe_preview = {k: (f"<text {len(v)} chars>" if isinstance(v, str) and len(v) > 500 else v) for k, v in ingest_args.items()}
        print("\n入库参数预览:")
        print(json.dumps(safe_preview, ensure_ascii=False, indent=2, default=str))

        if not args.execute:
            print("\n当前为 dry-run。确认工具和参数正确后，加 --execute 真正入库。")
            return 0

        result = await client.call_tool(tool["name"], ingest_args)
        print("\n✅ 入库工具调用完成:")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:4000])

        verify = await client.call_tool("query_knowledge_hub", {
            "query": args.verify_query,
            "collection": args.collection or settings.mcp_rag_collection,
            "top_k": 5,
        })
        print("\n🔎 查询验证:")
        print(json.dumps(verify, ensure_ascii=False, indent=2, default=str)[:4000])
        return 0
    except httpx.ConnectError:
        print(f"❌ 无法连接 MCP RAG Server: {server_url}")
        print("请先启动 MCP RAG Server，再重新运行脚本。")
        return 2
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入 PDF 到 MCP RAG Server")
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("--server-url", help="MCP RAG Server URL，默认读取 MASSAGEOPS_MCP_RAG_SERVER_URL")
    parser.add_argument("--collection", default=None, help="目标 collection，默认读取 MASSAGEOPS_MCP_RAG_COLLECTION")
    parser.add_argument("--doc-id", default="massage_store_rules_business_manual", help="文档 ID")
    parser.add_argument("--title", default=None, help="文档标题，默认使用 PDF 文件名")
    parser.add_argument("--doc-type", default="store_rules", help="文档类型/分类")
    parser.add_argument("--tool", help="指定 MCP 入库工具名；不传则自动根据 tools/list 猜测")
    parser.add_argument("--timeout", type=float, default=120.0, help="MCP 请求超时时间")
    parser.add_argument("--verify-query", default="按摩店门规 预约取消 投诉处理 技师管理", help="入库后的验证查询")
    parser.add_argument("--extract-only", action="store_true", help="只提取 PDF 文本，不连接 MCP")
    parser.add_argument("--execute", action="store_true", help="真正调用 MCP 入库工具；默认 dry-run")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
