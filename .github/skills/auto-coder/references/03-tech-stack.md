# 技术栈

## 后端

- Python 3.11
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- LangGraph
- pytest / pytest-asyncio / httpx

## 前端

- React
- TypeScript
- Vite
- lucide-react
- Vitest
- Testing Library

## 本地开发

- 后端虚拟环境：`backend/.venv`
- 快速演示数据库：`sqlite+aiosqlite:///./dev.db`
- 快速演示 Redis：`memory://`
- 正式本地编排：`docker-compose.yml`

## 重要目录

- `backend/app/agents`
- `backend/app/harness`
- `backend/app/services`
- `backend/app/models`
- `backend/app/api/v1/routes`
- `frontend/src/features/chat`
- `frontend/src/features/agent-runs`
