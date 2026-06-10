# 作用：统一的 LLM 调用接口，支持 OpenAI-compatible API（DeepSeek / Qwen / Claude / 本地模型）。
# Agent 层不直接依赖具体 provider，通过这里做适配，方便切换和测试。
import json
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# 通用 LLM 响应模型
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """一条聊天消息。"""
    role: str  # system | user | assistant
    content: str


class ChatUsage(BaseModel):
    """token 用量统计。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """LLM 文本响应。"""
    content: str
    usage: ChatUsage | None = None
    model: str | None = None


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------


class BaseModelProvider(ABC):
    """LLM Provider 抽象基类。

    所有具体 provider 必须实现 chat / chat_structured / embed 三个方法。
    """

    @abstractmethod
    async def chat(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatResponse:
        """发送对话消息，返回文本响应。"""
        ...

    @abstractmethod
    async def chat_structured(
        self,
        *,
        messages: list[ChatMessage],
        schema: type[T],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> T:
        """发送对话消息，返回符合 Pydantic Schema 的结构化输出。"""
        ...

    @abstractmethod
    async def embed(self, *, texts: list[str], model: str | None = None) -> list[list[float]]:
        """文本向量化，返回 embedding 列表。"""
        ...


# ---------------------------------------------------------------------------
# OpenAI-compatible 实现（覆盖 DeepSeek / Qwen / Claude / vLLM 等）
# ---------------------------------------------------------------------------

_OPENAI_COMPATIBLE_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "chat_model": "gpt-4o",
        "embed_model": "text-embedding-3-small",
    },
    "deepseek": {
        "chat_model": "deepseek-chat",
        "embed_model": "",  # DeepSeek 暂不提供 embedding
    },
    "qwen": {
        "chat_model": "qwen-plus",
        "embed_model": "text-embedding-v3",
    },
    "claude": {
        "chat_model": "claude-sonnet-4-6",
        "embed_model": "",  # Anthropic 不提供独立的 embedding 接口
    },
}


class OpenAICompatibleProvider(BaseModelProvider):
    """OpenAI-compatible API 通用适配器。

    通过环境变量 MASSAGEOPS_LLM_* 控制：
    - MASSAGEOPS_LLM_PROVIDER:   provider 名称（openai / deepseek / qwen / claude）
    - MASSAGEOPS_LLM_BASE_URL:   自定义 API 地址（留空则用 provider 默认值）
    - MASSAGEOPS_LLM_API_KEY:    API Key
    - MASSAGEOPS_LLM_CHAT_MODEL: 覆盖默认 chat 模型
    - MASSAGEOPS_LLM_EMBED_MODEL: 覆盖默认 embedding 模型
    """

    _DEFAULT_BASE_URLS: dict[str, str] = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "claude": "https://api.anthropic.com/v1",
    }

    def __init__(self) -> None:
        settings = get_settings()
        self.provider_name: str = settings.llm_provider
        self.base_url: str = settings.llm_base_url or self._DEFAULT_BASE_URLS.get(self.provider_name, "")
        self.api_key: str = settings.llm_api_key or os.getenv("MASSAGEOPS_LLM_API_KEY", "sk-placeholder")
        self.chat_model: str = settings.llm_chat_model or _OPENAI_COMPATIBLE_DEFAULTS.get(self.provider_name, {}).get("chat_model", "gpt-4o")
        self.embed_model: str = settings.llm_embed_model or _OPENAI_COMPATIBLE_DEFAULTS.get(self.provider_name, {}).get("embed_model", "text-embedding-3-small")

        self._client: AsyncOpenAI = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    # ------------------------------------------------------------------
    # chat
    # ------------------------------------------------------------------

    async def chat(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatResponse:
        """发送对话请求，返回纯文本。"""
        completion = await self._client.chat.completions.create(
            model=model or self.chat_model,
            messages=[m.model_dump(mode="json") for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        choice = completion.choices[0]
        return ChatResponse(
            content=choice.message.content or "",
            usage=ChatUsage(
                prompt_tokens=completion.usage.prompt_tokens if completion.usage else 0,
                completion_tokens=completion.usage.completion_tokens if completion.usage else 0,
                total_tokens=completion.usage.total_tokens if completion.usage else 0,
            ),
            model=completion.model,
        )

    # ------------------------------------------------------------------
    # chat_structured（利用 OpenAI response_format + json_schema）
    # ------------------------------------------------------------------

    async def chat_structured(
        self,
        *,
        messages: list[ChatMessage],
        schema: type[T],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> T:
        """发送对话请求，返回符合 Pydantic Schema 的结构化对象。

        使用 json_object 模式让 LLM 返回合法 JSON，再由 Pydantic 校验。
        比 strict json_schema 更兼容嵌套模型和可选字段。
        """
        # 将 Pydantic schema 转为简洁的 JSON 格式说明，内嵌到 system prompt 末尾
        schema_desc = _schema_to_description(schema)
        augmented = list(messages)
        augmented.append(ChatMessage(
            role="system",
            content=f"请严格按以下 JSON 格式回复（不要多余文本，只输出 JSON）：\n{schema_desc}",
        ))

        completion = await self._client.chat.completions.create(
            model=model or self.chat_model,
            messages=[m.model_dump(mode="json") for m in augmented],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **kwargs,
        )
        raw = completion.choices[0].message.content or "{}"
        return schema.model_validate(json.loads(raw))

    # ------------------------------------------------------------------
    # embed
    # ------------------------------------------------------------------

    async def embed(self, *, texts: list[str], model: str | None = None) -> list[list[float]]:
        """文本向量化。"""
        if not self.embed_model and not model:
            raise ValueError(
                f"Embedding model not configured for provider '{self.provider_name}'. "
                "Set MASSAGEOPS_LLM_EMBED_MODEL to enable embeddings."
            )
        response = await self._client.embeddings.create(
            model=model or self.embed_model,
            input=texts,
        )
        return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _schema_to_description(model: type[BaseModel]) -> str:
    """将 Pydantic 模型转为人类可读的 JSON 格式说明，供 LLM 输出参考。

    生成类似 {"task_type": "book_appointment", "slots": {...}, ...} 的结构说明。
    LLM 按此格式输出 JSON，再由 Pydantic 校验保证正确性。
    """
    raw = model.model_json_schema()
    props = raw.get("properties", {})

    def _describe_field(name: str, prop: dict) -> str:
        desc = prop.get("description", "")
        type_ = prop.get("type", "string")
        if "anyOf" in prop:
            types = [t.get("type", "string") for t in prop["anyOf"]]
            type_ = " | ".join(t for t in types if t != "null") + " | null"
        ref = prop.get("$ref", "")
        if ref:
            # 解析 $defs 引用
            def_name = ref.split("/")[-1]
            def_schema = raw.get("$defs", {}).get(def_name, {})
            if def_schema:
                nested = _describe_properties(def_schema.get("properties", {}))
                return f"{name}: {{ {nested} }}" + (f"  // {desc}" if desc else "")
        if type_ == "array":
            items = prop.get("items", {})
            item_type = items.get("type", "string")
            return f"{name}: [{item_type}, ...]" + (f"  // {desc}" if desc else "")
        if type_ == "object":
            nested = _describe_properties(prop.get("properties", {}))
            return f"{name}: {{ {nested} }}" + (f"  // {desc}" if desc else "")
        return f"{name}: {type_}" + (f"  // {desc}" if desc else "")

    def _describe_properties(props: dict) -> str:
        return ", ".join(_describe_field(k, v) for k, v in props.items())

    desc = _describe_properties(props)
    required = raw.get("required", [])
    req_note = f" 必填字段: {', '.join(required)}。" if required else ""
    return f"{{ {desc} }}{req_note}"


def create_model_provider() -> BaseModelProvider:
    """工厂函数：根据配置创建 LLM provider 实例。"""
    return OpenAICompatibleProvider()
