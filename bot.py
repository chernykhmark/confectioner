import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from handlers import register_all_routers
from middlewares.relay_mw import RelayMiddleware
from services.scheduler import setup_scheduler


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # relay-перехват сообщений юзера — раньше роутеров
    dp.message.middleware(RelayMiddleware())

    register_all_routers(dp)

    setup_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())