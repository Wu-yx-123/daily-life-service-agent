# 作用：统一生成语义记忆向量，优先使用模型服务，失败时用本地确定性向量兜底。
from __future__ import annotations

import hashlib
import math

EMBEDDING_DIMENSION = 1536


class EmbeddingService:
    """Embedding 服务。

    生产环境优先走 ModelProvider 的 embedding API；本地演示或没有 embedding key 时，
    使用确定性哈希向量兜底，保证 pgvector 语义记忆链路仍然可测试。
    """

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_texts([text]))[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            from app.core.model_provider import create_model_provider

            vectors = await create_model_provider().embed(texts=texts)
            if vectors and len(vectors[0]) == EMBEDDING_DIMENSION:
                return vectors
        except Exception:
            pass
        return [_deterministic_embedding(text) for text in texts]


def _deterministic_embedding(text: str) -> list[float]:
    """把文本稳定映射到固定维度向量。

    这不是高质量语义模型，但足够让本地测试覆盖“写入 pgvector → 相似度召回”闭环。
    """
    vector = [0.0] * EMBEDDING_DIMENSION
    tokens = [token for token in text.replace("，", " ").replace("。", " ").split() if token]
    if not tokens:
        tokens = [text or "empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [round(item / norm, 8) for item in vector]


def vector_to_pg_literal(vector: list[float]) -> str:
    """转换为 pgvector 可接收的字符串格式，例如 [0.1,0.2,...]。"""
    return "[" + ",".join(str(float(item)) for item in vector) + "]"
