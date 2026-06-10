# 作用：账号密码认证与 JWT 签发/校验工具。
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from app.core.config import get_settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str, salt: bytes | None = None) -> str:
    """使用 PBKDF2-HMAC-SHA256 保存密码，返回可入库字符串。"""
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"pbkdf2_sha256$120000${_b64url(salt)}${_b64url(digest)}"


def verify_password(password: str, password_hash: str | None) -> bool:
    """校验明文密码和入库哈希是否匹配。"""
    if not password_hash:
        return False
    try:
        scheme, iterations, salt_text, digest_text = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = _b64url_decode(salt_text)
        expected = _b64url_decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(*, subject: str, role: str, username: str, login_as: str) -> str:
    """签发 HS256 JWT。"""
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": subject,
        "username": username,
        "role": role,
        "login_as": login_as,
        "iat": now,
        "exp": now + settings.jwt_expires_seconds,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    """校验并解析 JWT，失败时抛出 ValueError。"""
    settings = get_settings()
    try:
        header_text, payload_text, signature_text = token.split(".")
        signing_input = f"{header_text}.{payload_text}"
        expected = hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(signature_text)):
            raise ValueError("invalid token signature")
        payload = json.loads(_b64url_decode(payload_text))
    except Exception as exc:
        raise ValueError("invalid token") from exc
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("token expired")
    return payload
