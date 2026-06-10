# 作用：构建 FastAPI 后端容器，运行 MassageOps-Agent API。
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN pip install --no-cache-dir -e .

# 创建非 root 用户并赋予文件权限
RUN useradd --system --user-group --home-dir /app appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["bash", "scripts/docker_entrypoint.sh"]
