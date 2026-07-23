import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from database.db import init_db
from handlers import client, admin
from middlewares.subscription import SubscriptionCheckMiddleware
from utils.notifications import check_and_send_reminders

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    logger.info("Starting up...")
    await init_db()
    logger.info("Database initialized.")


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.startup.register(on_startup)

    dp.include_router(client.router)
    dp.include_router(admin.router)

    dp.message.middleware(SubscriptionCheckMiddleware(bot))
    dp.callback_query.middleware(SubscriptionCheckMiddleware(bot))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_and_send_reminders,
        trigger="interval",
        minutes=15,
        args=(bot,),
        id="reminder_check",
        replace_existing=True,
    )
    scheduler.start()

    logger.info("Bot started polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
