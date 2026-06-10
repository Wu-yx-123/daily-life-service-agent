# 作用：通过 MCP Streamable HTTP + SSE 协议连接外部 Agentic RAG Server。
# 返回结构化的 evidence 片段供 KnowledgeAgent 和售后工单 policy_basis 使用。
import json
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


class MCPRagError(Exception):
    pass


class MCPRagClient:
    """MCP Streamable HTTP + SSE 客户端。"""

    def __init__(self, server_url: str, *, timeout: float = 30.0) -> None:
        self._url: str = server_url.rstrip("/")
        self._timeout: float = timeout
        self._http: httpx.AsyncClient | None = None
        self._session_id: str | None = None
        self._request_id: int = 0
        self._initialized: bool = False

    @property
    def available(self) -> bool:
        return self._initialized

    async def initialize(self) -> bool:
        if self._initialized:
            return True
        if not self._url:
            return False
        try:
            client = await self._get_http()
            resp = await client.post(self._url, json={
                "jsonrpc": JSONRPC_VERSION, "id": self._next_id(), "method": "initialize",
                "params": {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {},
                           "clientInfo": {"name": "massageops-agent", "version": "0.1.0"}},
            })
            result = self._parse_response(resp)
            sid = resp.headers.get("mcp-session-id")
            if sid:
                self._session_id = sid
            logger.info("MCP RAG Server 在线: %s (session=%s)",
                        result.get("serverInfo", {}).get("name", "?"), self._session_id)
            await self._notify("notifications/initialized", {})
            self._initialized = True
            return True
        except Exception as exc:
            logger.warning("MCP RAG Server 初始化失败: %s", exc)
            return False

    async def search(self, *, query: str, collection: str | None = None, top_k: int = 5) -> dict[str, Any]:
        if not self._initialized:
            ok = await self.initialize()
            if not ok:
                raise MCPRagError("MCP RAG Server 未连接")
        arguments: dict[str, Any] = {"query": query, "top_k": top_k}
        if collection:
            arguments["collection"] = collection
        raw = await self._rpc("tools/call", params={"name": "query_knowledge_hub", "arguments": arguments})
        normalized = self._normalize_response(raw)
        normalized["source"] = "mcp_rag"
        return normalized

    async def list_collections(self, *, include_stats: bool = True) -> list[dict[str, Any]]:
        """列出所有知识库 collection。"""
        if not self._initialized:
            ok = await self.initialize()
            if not ok:
                raise MCPRagError("MCP RAG Server 未连接")
        raw = await self._rpc("tools/call", params={"name": "list_collections", "arguments": {"include_stats": include_stats}})
        content = raw.get("content", [])
        for block in content:
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return []

    async def get_document_summary(self, *, doc_id: str, collection: str | None = None) -> dict[str, Any]:
        """获取指定文档的摘要和元数据。"""
        if not self._initialized:
            ok = await self.initialize()
            if not ok:
                raise MCPRagError("MCP RAG Server 未连接")
        args: dict[str, Any] = {"doc_id": doc_id}
        if collection:
            args["collection"] = collection
        raw = await self._rpc("tools/call", params={"name": "get_document_summary", "arguments": args})
        content = raw.get("content", [])
        for block in content:
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except (json.JSONDecodeError, TypeError):
                    return {"text": block.get("text", "")}
        return {}

    async def ingest_document(
        self,
        *,
        file_path: str,
        collection: str,
        force: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """调用 MCP RAG Server 的 `ingest_document` 工具触发文档入库。"""
        if not self._initialized:
            ok = await self.initialize()
            if not ok:
                raise MCPRagError("MCP RAG Server 未连接")
        raw = await self._rpc(
            "tools/call",
            params={
                "name": "ingest_document",
                "arguments": {
                    "file_path": file_path,
                    "collection": collection,
                    "force": force,
                    "dry_run": dry_run,
                },
            },
        )
        return self._parse_tool_json_payload(raw)

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None
            self._initialized = False

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self._timeout, headers={**HEADERS}, trust_env=False)
        return self._http

    def _headers(self) -> dict[str, str]:
        return {"mcp-session-id": self._session_id} if self._session_id else {}

    async def _rpc(self, method: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        client = await self._get_http()
        payload = {"jsonrpc": JSONRPC_VERSION, "id": self._next_id(), "method": method, "params": params or {}}
        try:
            resp = await client.post(self._url, json=payload, headers=self._headers())
            resp.raise_for_status()
            result = self._parse_response(resp)
        except httpx.TimeoutException:
            raise MCPRagError(f"MCP RAG Server 超时 ({self._timeout}s)")
        except httpx.HTTPError as exc:
            raise MCPRagError(f"MCP RAG Server HTTP 错误: {exc}")
        if "error" in result:
            err = result["error"]
            raise MCPRagError(f"MCP 错误 [{err.get('code')}]: {err.get('message', 'unknown')}")
        return result

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        try:
            client = await self._get_http()
            await client.post(self._url, json={"jsonrpc": JSONRPC_VERSION, "method": method, "params": params},
                              headers=self._headers())
        except Exception:
            pass

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict[str, Any]:
        if "text/event-stream" in resp.headers.get("content-type", ""):
            return MCPRagClient._parse_sse(resp.text)
        try:
            return resp.json()
        except Exception:
            return {}

    @staticmethod
    def _parse_sse(text: str) -> dict[str, Any]:
        for block in re.split(r"\n\n", text.strip()):
            data_lines = [line[6:] for line in block.split("\n") if line.startswith("data: ")]
            if data_lines:
                try:
                    parsed = json.loads("\n".join(data_lines))
                    if isinstance(parsed, dict) and "result" in parsed:
                        return parsed["result"]
                except json.JSONDecodeError:
                    continue
        return {}

    @staticmethod
    def _normalize_response(raw: dict[str, Any]) -> dict[str, Any]:
        """标准化为 {answer, evidence, hits}。evidence 含可追溯的 source_file/doc_type/chunk_id/score/text。"""
        content_list = raw.get("content", [])
        evidence: list[dict[str, Any]] = []
        hits: list[dict[str, Any]] = []
        answer: str = ""

        for block in content_list:
            if block.get("type") != "text":
                continue
            text: str = block.get("text", "")

            json_match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    for cite in (parsed.get("citations") or []):
                        meta = cite.get("metadata", {})
                        src = cite.get("source", "")
                        evidence.append({
                            "source_file": src.split("/")[-1] if "/" in src else src,
                            "doc_type": meta.get("doc_type", ""),
                            "chunk_id": cite.get("chunk_id", ""),
                            "score": cite.get("score", 0.0),
                            "text": cite.get("text_snippet", ""),
                        })
                        hits.append({
                            "id": cite.get("chunk_id", ""), "title": meta.get("title", ""),
                            "category": meta.get("doc_type", ""), "content": cite.get("text_snippet", ""),
                            "score": cite.get("score", 0.0), "source": src,
                        })
                    if evidence:
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass

            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    answer = parsed.get("answer", answer)
                    for doc in (parsed.get("documents") or parsed.get("hits") or []):
                        meta = doc.get("metadata", {}) if isinstance(doc.get("metadata"), dict) else {}
                        evidence.append({
                            "source_file": doc.get("source_file", meta.get("source", "")),
                            "doc_type": doc.get("doc_type", meta.get("category", "")),
                            "chunk_id": doc.get("chunk_id", doc.get("id", "")),
                            "score": doc.get("score", doc.get("relevance", 1.0)),
                            "text": doc.get("text", doc.get("content", "")),
                        })
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

            answer = answer or text

        if not answer and hits:
            answer = "；".join(f"{h['title']}：{h['content'][:200]}" for h in hits[:2])
        if not answer:
            answer = "（RAG Server 返回了空结果）"

        return {"answer": answer, "evidence": evidence, "hits": hits}

    @staticmethod
    def _parse_tool_json_payload(raw: dict[str, Any]) -> dict[str, Any]:
        """解析 MCP TextContent 中的 JSON 或 fenced JSON。"""
        for block in raw.get("content", []):
            if block.get("type") != "text":
                continue
            text = block.get("text", "")
            json_match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
            candidate = json_match.group(1) if json_match else text
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    parsed.setdefault("is_error", bool(raw.get("isError", False)))
                    return parsed
            except (json.JSONDecodeError, TypeError):
                continue
        return {"is_error": bool(raw.get("isError", False)), "raw": raw}


_rag_client: MCPRagClient | None = None


def get_mcp_rag_client() -> MCPRagClient:
    global _rag_client
    if _rag_client is None:
        s = get_settings()
        _rag_client = MCPRagClient(server_url=s.mcp_rag_server_url, timeout=s.mcp_rag_timeout)
    return _rag_client
