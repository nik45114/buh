"""
Главный файл приложения - запуск бота и API
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.config import settings
from app.database.db import init_db, close_db
from app.bot.handlers import owner, admin, common, receipt, employees, payroll, ofd_check, manual_check
from app.services.scheduler import setup_scheduler, start_scheduler, stop_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/accounting_bot.log')
    ]
)
logger = logging.getLogger(__name__)


async def start_bot():
    """Запуск Telegram бота"""
    try:
        # Инициализация БД
        await init_db()

        # Инициализация бота
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        # Storage для FSM
        storage = MemoryStorage()

        # Диспетчер
        dp = Dispatcher(storage=storage)

        # Регистрация handlers (порядок важен!)
        dp.include_router(owner.router)  # Владелец (самые высокие права)
        dp.include_router(admin.router)  # Админы
        dp.include_router(employees.router)  # Сотрудники
        dp.include_router(payroll.router)  # Зарплата
        dp.include_router(manual_check.router)  # Ручная проверка смен
        dp.include_router(ofd_check.router)  # Проверка с СБИС ОФД
        dp.include_router(receipt.router)  # Обработка фото
        dp.include_router(common.router)  # Общие команды

        # Запуск планировщика задач
        setup_scheduler()
        start_scheduler()
        logger.info("Scheduler started")

        logger.info("Starting Accounting Bot...")
        logger.info(f"Company: {settings.COMPANY_NAME}")
        logger.info(f"Tax system: {settings.TAX_SYSTEM}")
        logger.info(f"Owner ID: {settings.OWNER_TELEGRAM_ID}")

        # Запуск polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise
    finally:
        stop_scheduler()
        await close_db()


async def start_api_server():
    """Запуск API сервера"""
    import uvicorn
    from app.api.main import app

    config = uvicorn.Config(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)

    logger.info(f"Starting API server on {settings.API_HOST}:{settings.API_PORT}")

    await server.serve()


async def main():
    """
    Главная функция
    Запускает бота и API сервер одновременно
    """
    # Выбор режима работы из переменной окружения
    import os
    mode = os.environ.get('RUN_MODE', 'bot')

    if mode == 'bot':
        # Запуск только бота
        await start_bot()
    elif mode == 'api':
        # Запуск только API
        await start_api_server()
    elif mode == 'both':
        # Запуск бота и API вместе
        await asyncio.gather(
            start_bot(),
            start_api_server()
        )
    else:
        logger.error(f"Unknown RUN_MODE: {mode}. Use 'bot', 'api', or 'both'")
        sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
