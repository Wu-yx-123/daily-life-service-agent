# 作用：验证 Demo 门店排班覆盖早8点到晚12点，且 6 位技师都在岗。
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.business import Store, Technician, TechnicianSchedule


async def test_demo_schedule_should_cover_all_technicians_from_8_to_midnight(db_session):
    store = await db_session.scalar(select(Store).where(Store.status == "active"))
    assert store is not None
    assert store.opening_time.hour == 8
    assert store.closing_time.hour == 23

    technicians = list((await db_session.scalars(select(Technician).where(Technician.status == "active"))).all())
    assert len(technicians) >= 6

    target_date = datetime.now().date() + timedelta(days=9)
    schedules = list(
        (
            await db_session.scalars(
                select(TechnicianSchedule).where(
                    TechnicianSchedule.work_date == target_date,
                    TechnicianSchedule.status == "available",
                )
            )
        ).all()
    )

    assert {schedule.technician_id for schedule in schedules} >= {tech.id for tech in technicians}
    for schedule in schedules:
        assert schedule.start_time <= datetime.combine(target_date, store.opening_time)
        assert schedule.end_time >= datetime.combine(target_date + timedelta(days=1), store.closing_time.replace(hour=0, minute=0, second=0))
