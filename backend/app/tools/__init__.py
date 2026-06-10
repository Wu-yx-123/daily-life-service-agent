# 作用：工具包入口，集中导出所有 Agent 可调用的工具函数。
# 每个工具模块包含无状态的 async 函数，由 ToolRegistry 注册后供 Agent 调用。

from app.tools.service_tools import (
    get_service_detail,
    search_services,
    search_stores,
    search_technicians,
)
from app.tools.schedule_tools import (
    check_schedule,
    create_time_lock,
    release_time_lock,
)
from app.tools.order_tools import (
    check_order_conflicts,
    create_order,
    get_order,
    list_user_orders,
)
from app.tools.price_tools import (
    calculate_discounted_price,
    calculate_price,
    list_available_coupons,
)
from app.tools.risk_tools import (
    check_user_risk,
    create_risk_record,
)
from app.tools.search_tools import (
    search_knowledge,
    search_services_by_keyword,
)
from app.tools.notification_tools import (
    notify_admin,
    send_after_sales_notification,
    send_booking_confirmation,
)

__all__ = [
    # service
    "search_services",
    "get_service_detail",
    "search_technicians",
    "search_stores",
    # schedule
    "check_schedule",
    "create_time_lock",
    "release_time_lock",
    # order
    "create_order",
    "get_order",
    "list_user_orders",
    "check_order_conflicts",
    # price
    "calculate_price",
    "list_available_coupons",
    "calculate_discounted_price",
    # risk
    "check_user_risk",
    "create_risk_record",
    # search
    "search_knowledge",
    "search_services_by_keyword",
    # notification
    "send_booking_confirmation",
    "notify_admin",
    "send_after_sales_notification",
]
