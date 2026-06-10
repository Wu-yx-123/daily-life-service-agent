# 作用：PostgreSQL 原生 UUID 类型别名。
from sqlalchemy.dialects.postgresql import UUID as _PG_UUID


def GUID():
    """PostgreSQL 原生 UUID 列类型。"""
    return _PG_UUID(as_uuid=True)
