#!/bin/bash
# Docker 容器入口：数据库迁移 → Demo 数据 → 启动 FastAPI
set -e

echo "=== 1/3 数据库迁移 ==="
alembic upgrade head

echo "=== 2/3 Demo 数据 ==="
python scripts/seed_demo_data.py

echo "=== 3/3 启动应用 ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
