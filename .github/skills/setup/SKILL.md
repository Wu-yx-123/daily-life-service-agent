---
name: setup
description: "MassageOps-Agent 项目本地环境配置与启动向导。Use when 用户说“setup”“初始化项目”“配置环境”“启动项目”“first run”“quick start”“跑起来”“安装依赖”，或希望创建 backend/.venv、安装 Python/npm 依赖、配置 SQLite/memory Redis 或 Docker Compose 并启动 FastAPI + React 时使用。"
---

# Setup — MassageOps-Agent

## 目标

帮助用户从当前仓库启动项目。

## 本地快速启动

### 1. 后端虚拟环境

```bash
cd "/Users/wuyuxuan/VScode/Daily Life Service Agent"
python3.11 -m venv backend/.venv
source backend/.venv/bin/activate
cd backend
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### 2. 前端依赖

```bash
cd frontend
npm install
```

### 3. 启动后端

```bash
cd backend
source .venv/bin/activate
MASSAGEOPS_DATABASE_URL=sqlite+aiosqlite:///./dev.db \
MASSAGEOPS_REDIS_URL=memory:// \
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 启动前端

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

访问：

- 前端：http://localhost:5173
- 后端：http://localhost:8000/docs

## Docker 启动

Docker daemon 已运行时：

```bash
docker compose up --build
```

## 验证

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/docs
curl -s -o /dev/null -w '%{http_code}' http://localhost:5173/
```

都返回 `200` 即启动成功。

## 参考

- `references/provider_profiles.md`
- `references/new_provider_guide.md`
- `references/settings_template.yaml`
