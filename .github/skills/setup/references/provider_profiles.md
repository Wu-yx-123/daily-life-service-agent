# 当前项目环境配置说明

## 推荐本地开发配置

```bash
MASSAGEOPS_DATABASE_URL=sqlite+aiosqlite:///./dev.db
MASSAGEOPS_REDIS_URL=memory://
```

适合快速演示和开发，不需要本机安装 PostgreSQL/Redis。

## Docker 配置

```bash
MASSAGEOPS_DATABASE_URL=postgresql+asyncpg://massageops:massageops@postgres:5432/massageops
MASSAGEOPS_REDIS_URL=redis://redis:6379/0
```

由 `docker-compose.yml` 提供 Postgres 和 Redis。

## 前端配置

开发时 Vite 代理 `/api` 到 `http://localhost:8000`。

如果需要显式指定：

```bash
VITE_API_BASE=http://localhost:8000
```
