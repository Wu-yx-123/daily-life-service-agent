# 作用：账号密码登录，签发 JWT，并按用户选择的端进行角色准入。
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.business import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    login_as: str = "customer"  # customer | merchant


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    nickname: str | None
    phone: str | None
    role: str
    login_as: str
    member_level: str | None


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """账号密码登录。

    规则：
    - merchant 账号可以选择 customer 或 merchant 端登录
    - customer 账号只能选择 customer 端登录
    """
    login_as = payload.login_as
    if login_as not in {"customer", "merchant"}:
        raise HTTPException(status_code=422, detail="login_as must be customer or merchant")

    user = (await db.scalars(select(User).where(User.username == payload.username))).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    if login_as == "merchant" and user.role != "merchant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="消费者账号不能登录商家端")

    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        username=user.username or payload.username,
        login_as=login_as,
    )
    return LoginResponse(
        access_token=token,
        user_id=str(user.id),
        username=user.username or payload.username,
        nickname=user.nickname,
        phone=user.phone,
        role=user.role,
        login_as=login_as,
        member_level=user.member_level,
    )
