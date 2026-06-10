# 作用：初始化完整演示数据，提供预约、售后和知识库 Demo 依赖。
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.business import KnowledgeDocument, Room, Service, Store, Technician, TechnicianSchedule, User

DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def ensure_demo_data(db: AsyncSession) -> None:
    """幂等写入 Demo 数据。

    该函数可被应用启动和 scripts/seed_demo_data.py 复用。
    """
    user = await db.scalar(select(User).where((User.username == "customer") | (User.id == DEMO_USER_ID) | (User.phone == "demo_user_001")))
    if not user:
        user = User(id=DEMO_USER_ID, username="customer", nickname="Demo User", phone="demo_user_001", member_level="silver", role="customer")
        db.add(user)
    user.username = "customer"
    user.role = "customer"
    user.nickname = user.nickname or "Demo User"
    user.phone = user.phone or "demo_user_001"
    user.member_level = user.member_level or "silver"
    if not user.password_hash:
        user.password_hash = hash_password("Customer@123")

    # 商家管理员
    merchant = await db.scalar(select(User).where((User.username == "merchant") | (User.phone == "merchant_001")))
    if not merchant:
        merchant = User(username="merchant", nickname="店长", phone="merchant_001", role="merchant", member_level="gold")
        db.add(merchant)
    merchant.username = "merchant"
    merchant.role = "merchant"
    merchant.nickname = merchant.nickname or "店长"
    merchant.phone = merchant.phone or "merchant_001"
    merchant.member_level = merchant.member_level or "gold"
    if not merchant.password_hash:
        merchant.password_hash = hash_password("Merchant@123")

    store = await db.scalar(select(Store).where(Store.name == "静心按摩 Tokyo 店"))
    if not store:
        store = Store(name="静心按摩 Tokyo 店", address="Tokyo demo street", opening_time=time(18, 0), closing_time=time(23, 0))
        db.add(store)
        await db.flush()
    store.opening_time = time(8, 0)
    store.closing_time = time(23, 59, 59)
    store.latitude = store.latitude or 35.681236
    store.longitude = store.longitude or 139.767125

    existing_services = {item.name for item in (await db.scalars(select(Service).where(Service.store_id == store.id))).all()}
    service_specs = [
        ("肩颈舒缓 60 分钟", "肩颈理疗", 60, Decimal("198"), ["肩颈", "久坐", "放松"]),
        ("深层经络 90 分钟", "中式推拿", 90, Decimal("328"), ["经络", "力度偏重", "疲劳恢复"]),
        ("全身放松 90 分钟", "全身按摩", 90, Decimal("298"), ["全身", "放松", "助眠"]),
        ("足底反射 60 分钟", "足疗", 60, Decimal("168"), ["足底", "反射区", "循环"]),
        ("运动拉伸 75 分钟", "运动康复", 75, Decimal("268"), ["拉伸", "筋膜", "运动恢复"]),
        ("精油 SPA 60 分钟", "芳香 SPA", 60, Decimal("268"), ["精油", "舒压", "轻柔"]),
        ("精油 SPA 90 分钟", "芳香 SPA", 90, Decimal("358"), ["精油", "舒压", "轻柔"]),
        ("精油 SPA 100 分钟", "芳香 SPA", 100, Decimal("398"), ["精油", "舒压", "轻柔"]),
    ]
    for name, category, duration, price, tags in service_specs:
        if name not in existing_services:
            db.add(Service(store_id=store.id, name=name, category=category, duration_minutes=duration, base_price=price, tags=tags))

    existing_techs = {item.name for item in (await db.scalars(select(Technician).where(Technician.store_id == store.id))).all()}
    tech_specs = [
        ("李师傅", ["肩颈理疗", "力度偏重", "深层经络"], Decimal("4.8")),
        ("王老师", ["全身放松", "助眠舒压", "力度适中"], Decimal("4.7")),
        ("陈师傅", ["运动拉伸", "筋膜放松", "康复护理"], Decimal("4.9")),
        ("赵老师", ["足底反射", "腿部放松", "循环改善"], Decimal("4.6")),
        ("刘师傅", ["中式推拿", "腰背调理", "疲劳恢复"], Decimal("4.8")),
        ("周老师", ["精油 SPA", "轻柔舒压", "女性护理"], Decimal("4.9")),
    ]
    for name, tags, rating in tech_specs:
        if name not in existing_techs:
            db.add(Technician(store_id=store.id, name=name, skill_tags=tags, rating=rating))

    existing_rooms = {item.name for item in (await db.scalars(select(Room).where(Room.store_id == store.id))).all()}
    for name in ["A101", "A102", "A103", "A104", "A105", "A106"]:
        if name not in existing_rooms:
            db.add(Room(store_id=store.id, name=name))

    await db.flush()
    techs = list((await db.scalars(select(Technician).where(Technician.store_id == store.id))).all())
    today = datetime.now().date()
    for work_date in [today + timedelta(days=offset) for offset in range(14)]:
        for tech in techs:
            existing_schedule = await db.scalar(
                select(TechnicianSchedule).where(TechnicianSchedule.technician_id == tech.id, TechnicianSchedule.work_date == work_date)
            )
            if not existing_schedule:
                db.add(
                    TechnicianSchedule(
                        technician_id=tech.id,
                        store_id=store.id,
                        work_date=work_date,
                        start_time=datetime.combine(work_date, time(8, 0)),
                        end_time=datetime.combine(work_date + timedelta(days=1), time(0, 10)),
                    )
                )

    knowledge_specs = [
        ("预约取消规则", "after_sales_policy", "服务开始前 2 小时以上可免费取消；2 小时内取消需人工审核，可能收取爽约费用。", ["取消", "售后"]),
        ("退款处理规则", "after_sales_policy", "未服务订单可申请原路退款；已完成服务的退款需结合评价、投诉和门店记录人工复核。", ["退款", "售后"]),
        ("改期处理规则", "after_sales_policy", "改期必须重新检查技师排班、房间空闲和原订单状态，确认后释放原时段。", ["改期", "排班"]),
        ("投诉处理规则", "after_sales_policy", "投诉类请求需优先联系用户，保留 Trace、订单、技师和房间上下文，并由管理员跟进。", ["投诉", "人工"]),
        ("肩颈舒缓服务说明", "service_guide", "肩颈舒缓适合久坐和肩颈紧张用户，90 分钟项目会包含肩颈、上背和放松收尾。", ["肩颈", "服务"]),
    ]
    for title, category, content, tags in knowledge_specs:
        existing_doc = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.title == title))
        if not existing_doc:
            db.add(KnowledgeDocument(title=title, category=category, content=content, tags=tags))
    await db.commit()
