"""
Планировщик автоматических задач
"""
import logging
from datetime import date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.db import async_session
from .shift_importer import ShiftImporter
from .reminder_service import ReminderService

logger = logging.getLogger(__name__)

# Глобальный планировщик
scheduler = AsyncIOScheduler()


async def import_shifts_daily():
    """Импорт смен каждую ночь в 02:00"""
    try:
        async with async_session() as session:
            importer = ShiftImporter(session)

            # Импортировать вчерашний день
            yesterday = date.today() - timedelta(days=1)
            stats = await importer.import_shifts(yesterday, yesterday)

            logger.info(f"Daily shift import completed: {stats}")

            # Также импортировать отчеты о сменах
            reports_count = await importer.import_shift_reports(yesterday, yesterday)
            logger.info(f"Imported {reports_count} shift reports")

    except Exception as e:
        logger.error(f"Error in daily shift import: {e}", exc_info=True)


async def check_reminders_daily():
    """Проверка напоминаний каждое утро в 09:00"""
    try:
        async with async_session() as session:
            reminder_service = ReminderService(session)
            await reminder_service.send_due_reminders()

    except Exception as e:
        logger.error(f"Error checking reminders: {e}", exc_info=True)


async def check_tax_deadlines_weekly():
    """Проверка налоговых сроков каждый понедельник в 10:00"""
    try:
        async with async_session() as session:
            reminder_service = ReminderService(session)
            await reminder_service.check_tax_deadlines()

    except Exception as e:
        logger.error(f"Error checking tax deadlines: {e}", exc_info=True)


def setup_scheduler():
    """Настройка планировщика задач"""

    # Импорт смен каждую ночь в 02:00
    scheduler.add_job(
        import_shifts_daily,
        CronTrigger(hour=2, minute=0),
        id='import_shifts_daily',
        name='Import shifts from Bot_Claude',
        replace_existing=True
    )

    # Проверка напоминаний каждое утро в 09:00
    scheduler.add_job(
        check_reminders_daily,
        CronTrigger(hour=9, minute=0),
        id='check_reminders_daily',
        name='Check daily reminders',
        replace_existing=True
    )

    # Проверка налоговых сроков каждый понедельник в 10:00
    scheduler.add_job(
        check_tax_deadlines_weekly,
        CronTrigger(day_of_week='mon', hour=10, minute=0),
        id='check_tax_deadlines_weekly',
        name='Check tax deadlines',
        replace_existing=True
    )

    logger.info("Scheduler configured with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} (ID: {job.id})")


def start_scheduler():
    """Запустить планировщик"""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Остановить планировщик"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
