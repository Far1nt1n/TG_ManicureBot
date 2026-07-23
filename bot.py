import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import router
from scheduler_tasks import start_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Запуск бота"""
    # Инициализация базы данных
    init_db()
    logger.info("База данных инициализирована")

    # Создание бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключение обработчиков
    dp.include_router(router)

    # Запуск планировщика напоминаний
    start_scheduler(bot)
    logger.info("Планировщик напоминаний запущен")

    # Удаление вебхука и запуск polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен!")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())