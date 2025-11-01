"""
Обработчики команд для проверки смен через СБИС ОФД
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from datetime import date, timedelta
from sqlalchemy import select

from ...database.db import async_session
from ...database.models import Shift
from ...services.sbis_ofd import validate_shift_with_ofd, get_shift_validation_report
from ..keyboards import get_admin_keyboard, get_owner_keyboard

router = Router()


@router.message(Command("check_shift"))
async def check_shift_handler(message: Message):
    """
    Проверить сегодняшнюю смену с кассой

    Использование: /check_shift
    """
    await message.answer("🔍 Проверяю смену с кассой СБИС ОФД...")

    async with async_session() as session:
        # Получить сегодняшнюю смену
        result = await session.execute(
            select(Shift)
            .where(Shift.date == date.today())
            .order_by(Shift.id.desc())
        )
        shift = result.scalar_one_or_none()

        if not shift:
            await message.answer(
                "❌ Смена за сегодня не найдена.\n"
                "Сначала закройте смену в Bot_Claude."
            )
            return

        # Получить отчет о проверке
        report = await get_shift_validation_report(
            shift_date=shift.date,
            fact_cash=float(shift.cash_fact or 0),
            fact_cashless=float(shift.cashless_fact or 0),
            fact_qr=float(shift.qr_payments or 0)
        )

        await message.answer(report)


@router.message(Command("check_shift_date"))
async def check_shift_date_handler(message: Message):
    """
    Проверить смену за конкретную дату

    Использование: /check_shift_date 15.01.2025
    """
    try:
        # Парсинг даты из команды
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Укажите дату:\n"
                "/check_shift_date 15.01.2025"
            )
            return

        date_str = args[1]
        shift_date = date.fromisoformat(date_str) if "-" in date_str else \
                     datetime.strptime(date_str, "%d.%m.%Y").date()

    except ValueError:
        await message.answer(
            "❌ Неправильный формат даты.\n"
            "Используйте: /check_shift_date 15.01.2025"
        )
        return

    await message.answer(f"🔍 Проверяю смену за {shift_date.strftime('%d.%m.%Y')}...")

    async with async_session() as session:
        # Получить смену за дату
        result = await session.execute(
            select(Shift)
            .where(Shift.date == shift_date)
            .order_by(Shift.id.desc())
        )
        shift = result.scalar_one_or_none()

        if not shift:
            await message.answer(
                f"❌ Смена за {shift_date.strftime('%d.%m.%Y')} не найдена."
            )
            return

        # Получить отчет о проверке
        report = await get_shift_validation_report(
            shift_date=shift.date,
            fact_cash=float(shift.cash_fact or 0),
            fact_cashless=float(shift.cashless_fact or 0),
            fact_qr=float(shift.qr_payments or 0)
        )

        await message.answer(report)


@router.message(Command("check_week"))
async def check_week_handler(message: Message):
    """
    Проверить все смены за последнюю неделю

    Использование: /check_week
    """
    await message.answer("🔍 Проверяю смены за последнюю неделю...")

    today = date.today()
    week_ago = today - timedelta(days=7)

    async with async_session() as session:
        # Получить смены за неделю
        result = await session.execute(
            select(Shift)
            .where(Shift.date >= week_ago, Shift.date <= today)
            .order_by(Shift.date.desc())
        )
        shifts = result.scalars().all()

        if not shifts:
            await message.answer("❌ Смены за последнюю неделю не найдены.")
            return

        # Проверить каждую смену
        issues = []
        all_ok = []

        for shift in shifts:
            validation = await validate_shift_with_ofd(
                shift_date=shift.date,
                fact_cash=float(shift.cash_fact or 0),
                fact_cashless=float(shift.cashless_fact or 0),
                fact_qr=float(shift.qr_payments or 0)
            )

            if validation["status"] == "warning":
                disc = validation["discrepancies"]
                issues.append({
                    "date": shift.date,
                    "diff_total": disc["total"]["diff"]
                })
            elif validation["status"] == "ok":
                all_ok.append(shift.date)

        # Сформировать отчет
        report = "📊 ПРОВЕРКА СМЕН ЗА НЕДЕЛЮ\n"
        report += "=" * 40 + "\n\n"

        if issues:
            report += "⚠️ РАСХОЖДЕНИЯ:\n\n"
            for issue in issues:
                report += f"📅 {issue['date'].strftime('%d.%m.%Y')}: "
                report += f"{issue['diff_total']:+,.0f} ₽\n"
            report += "\n"

        if all_ok:
            report += "✅ БЕЗ РАСХОЖДЕНИЙ:\n\n"
            for shift_date in all_ok:
                report += f"📅 {shift_date.strftime('%d.%m.%Y')}\n"

        if not issues and not all_ok:
            report += "❌ Не удалось проверить смены"

        await message.answer(report)


@router.message(Command("ofd_status"))
async def ofd_status_handler(message: Message):
    """
    Проверить подключение к СБИС ОФД

    Использование: /ofd_status
    """
    import os
    from ...services.sbis_ofd import SbisOFD

    token = os.getenv("SBIS_OFD_TOKEN")
    inn = os.getenv("COMPANY_INN")

    if not token or not inn:
        await message.answer(
            "❌ СБИС ОФД не настроен\n\n"
            "Добавьте в .env файл:\n"
            "SBIS_OFD_TOKEN=ваш_токен\n"
            "COMPANY_INN=ваш_инн"
        )
        return

    await message.answer("🔍 Проверяю подключение к СБИС ОФД...")

    # Попробовать получить данные
    sbis = SbisOFD(token, inn)
    shift_data = await sbis.get_shift_totals(date.today())

    if shift_data:
        await message.answer(
            "✅ СБИС ОФД подключен\n\n"
            f"📊 Данные за сегодня:\n"
            f"💰 Наличные: {shift_data['cash']:,.2f} ₽\n"
            f"💳 Безнал: {shift_data['cashless']:,.2f} ₽\n"
            f"📊 Итого: {shift_data['total']:,.2f} ₽\n"
            f"🧾 Чеков: {shift_data['receipts_count']}\n"
            f"📋 Смена №{shift_data['shift_number']}"
        )
    else:
        await message.answer(
            "⚠️ Не удалось получить данные с СБИС ОФД\n\n"
            "Проверьте:\n"
            "1. Правильность токена\n"
            "2. Доступ к API\n"
            "3. Закрыта ли смена на кассе"
        )


@router.message(Command("auto_check"))
async def auto_check_handler(message: Message):
    """
    Включить/выключить автоматическую проверку смен

    Использование: /auto_check on/off
    """
    # TODO: Реализовать сохранение настройки в БД
    await message.answer(
        "🔧 Функция в разработке\n\n"
        "Скоро можно будет включить автоматическую проверку каждой смены "
        "и получать уведомления о расхождениях."
    )


# ============= ИНТЕГРАЦИЯ С ЗАКРЫТИЕМ СМЕНЫ =============

async def validate_and_notify(
    shift_date: date,
    cash: float,
    cashless: float,
    qr: float,
    chat_id: int,
    bot
) -> bool:
    """
    Проверить смену и отправить уведомление

    Использовать в обработчике закрытия смены

    Args:
        shift_date: Дата смены
        cash: Наличные
        cashless: Безнал
        qr: QR платежи
        chat_id: ID чата для уведомления
        bot: Экземпляр бота

    Returns:
        True - смена совпадает
        False - есть расхождения
    """
    validation = await validate_shift_with_ofd(
        shift_date, cash, cashless, qr
    )

    if validation["status"] == "error":
        await bot.send_message(
            chat_id,
            f"❌ Ошибка проверки с СБИС ОФД:\n{validation['message']}"
        )
        return False

    elif validation["status"] == "warning":
        # Получить полный отчет
        report = await get_shift_validation_report(
            shift_date, cash, cashless, qr
        )

        await bot.send_message(
            chat_id,
            f"⚠️ ОБНАРУЖЕНЫ РАСХОЖДЕНИЯ!\n\n{report}"
        )
        return False

    else:
        await bot.send_message(
            chat_id,
            "✅ Смена совпадает с кассой"
        )
        return True
