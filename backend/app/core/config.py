# 作用：集中管理应用配置，支持通过环境变量覆盖数据库和 Redis 地址。
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# 在 Settings 实例化之前加载 .env，确保无论从哪个目录启动都能找到。
# 优先级：MASSAGEOPS_ENV_FILE 环境变量 > backend/.env > 项目根/.env
_ENV_FILE = os.getenv("MASSAGEOPS_ENV_FILE")
if _ENV_FILE:
    load_dotenv(_ENV_FILE)
else:
    # 从当前文件位置向上逐级查找 .env
    _config_dir = Path(__file__).resolve().parent.parent  # …/backend/app/core → …/backend/app
    for _candidate in [
        _config_dir / ".env",            # backend/app/.env
        _config_dir.parent / ".env",     # backend/.env
        _config_dir.parent.parent / ".env",  # 项目根/.env
    ]:
        if _candidate.exists():
            load_dotenv(str(_candidate))
            break


class Settings(BaseSettings):
    """应用配置入口 — 仅支持 PostgreSQL。"""

    app_name: str = "MassageOps-Agent"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://massageops:massageops@localhost:5432/massageops"
    test_database_url: str = "postgresql+asyncpg://massageops:massageops@localhost:5432/massageops_test"
    redis_url: str = "redis://localhost:6379/0"
    time_lock_ttl_seconds: int = 600
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    jwt_secret: str = "dev-massageops-change-me"
    jwt_expires_seconds: int = 60 * 60 * 8

    # ── LLM / ModelProvider ──────────────────────────────────────────
    llm_provider: str = "deepseek"           # openai | deepseek | qwen | claude
    llm_base_url: str = ""                    # 自定义 API 地址（留空用 provider 默认值）
    llm_api_key: str = ""                     # API Key
    llm_chat_model: str = ""                  # 覆盖默认 chat 模型
    llm_embed_model: str = ""                 # 覆盖默认 embedding 模型

    # ── MCP RAG Server（HTTP 模式）──────────────────────────────────
    mcp_rag_server_url: str = ""                  # 外部 MCP RAG Server 地址，如 "http://localhost:9000/mcp"
    mcp_rag_timeout: float = 30.0                 # MCP 调用超时（秒）
    mcp_rag_collection: str = "knowledge"         # 默认知识库 collection 名称

    # ── 高德地图 / 位置服务 ───────────────────────────────────────────
    amap_api_key: str = ""                        # 高德 Web 服务 API Key
    amap_timeout: float = 10.0                    # 高德 HTTP 调用超时（秒）

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MASSAGEOPS_", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
