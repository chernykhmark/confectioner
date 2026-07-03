from aiogram import Dispatcher

from handlers import common
from handlers.user import funnel, templates, order
from handlers.admin import orders, monitoring
from handlers.admin import relay as admin_relay

def register_all_routers(dp: Dispatcher):
    # порядок важен: сначала admin (специфичные callback), затем user, затем common (nav)
    dp.include_router(orders.router)
    dp.include_router(monitoring.router)
    dp.include_router(templates.router)
    dp.include_router(funnel.router)
    dp.include_router(order.router)
    dp.include_router(common.router)
    dp.include_router(admin_relay.router)