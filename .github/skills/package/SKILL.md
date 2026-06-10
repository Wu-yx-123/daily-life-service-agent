---
name: package
description: "清理、打包和交付 MassageOps-Agent 项目。Use when 用户说“打包项目”“清理项目”“准备提交”“准备压缩包”“清理缓存”“发布前整理”，或希望删除虚拟环境、node_modules、dist、__pycache__、dev.db 等本地产物并保留源码、测试、README、dev_spec.md 时使用。"
---

# Package — MassageOps-Agent

## 目标

把项目整理成适合提交、压缩或展示的干净状态。

## 清理命令

先 dry-run：

```bash
python .github/skills/package/scripts/clean.py
```

确认后执行：

```bash
python .github/skills/package/scripts/clean.py --execute
```

## 必须保留

- `dev_spec.md`
- `README.md`
- `.env.example`
- `docker-compose.yml`
- `backend/app`
- `backend/alembic`
- `backend/pyproject.toml`
- `frontend/src`
- `frontend/tests`
- `frontend/package.json`
- `frontend/package-lock.json`
- `.github/skills`

## 应清理

- `backend/.venv`
- `frontend/node_modules`
- `frontend/dist`
- `__pycache__`
- `.pytest_cache`
- `backend/dev.db`
- `.env`

## 交付前验证

```bash
cd backend && source .venv/bin/activate && python -m pytest app/tests -q
cd ../frontend && npm test && npm run build
```
