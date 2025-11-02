"""
Ручная проверка смен без СБИС ОФД API
Для случаев, когда API недоступен
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, datetime
from sqlalchemy import select
from decimal import Decimal

from ...database.db import async_session
from ...database.models import Shift
from ..keyboards import get_admin_keyboard

router = Router()


class ManualCheckStates(StatesGroup):
    """Состояния для ручной проверки смены"""
    waiting_for_date = State()
    waiting_for_cash = State()
    waiting_for_cashless = State()
    waiting_for_qr = State()


@router.message(Command("check_manual"))
async def start_manual_check(message: Message, state: FSMContext):
    """
    Ручная проверка смены - ввод данных с Z-отчета кассы

    Использование: /check_manual
    """
    await message.answer(
        "📝 РУЧНАЯ ПРОВЕРКА СМЕНЫ\n\n"
        "Я помогу сверить данные с кассой.\n"
        "Возьмите Z-отчет кассы и отвечайте на вопросы.\n\n"
        "📅 Введите дату смены (например: 01.11.2025)\n"
        "или отправьте 'сегодня' для сегодняшней даты:"
    )
    await state.set_state(ManualCheckStates.waiting_for_date)


@router.message(ManualCheckStates.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    """Обработка даты"""
    text = message.text.strip().lower()

    if text in ['сегодня', 'today']:
        shift_date = date.today()
    else:
        try:
            # Попробовать разные форматы
            if '.' in text:
                shift_date = datetime.strptime(text, "%d.%m.%Y").date()
            elif '-' in text:
                shift_date = date.fromisoformat(text)
            else:
                await message.answer(
                    "❌ Неправильный формат даты.\n"
                    "Используйте: 01.11.2025 или 'сегодня'"
                )
                return
        except ValueError:
            await message.answer(
                "❌ Неправильный формат даты.\n"
                "Используйте: 01.11.2025 или 'сегодня'"
            )
            return

    # Сохранить дату
    await state.update_data(shift_date=shift_date)

    # Проверить, есть ли смена в БД
    async with async_session() as session:
        result = await session.execute(
            select(Shift)
            .where(Shift.date == shift_date)
            .order_by(Shift.id.desc())
        )
        shift = result.scalar_one_or_none()

        if shift:
            await state.update_data(
                fact_cash=float(shift.cash_fact or 0),
                fact_cashless=float(shift.cashless_fact or 0),
                fact_qr=float(shift.qr_payments or 0)
            )

            await message.answer(
                f"✅ Смена за {shift_date.strftime('%d.%m.%Y')} найдена!\n\n"
                f"📊 Данные из Bot_Claude:\n"
                f"💰 Наличные: {shift.cash_fact:,.2f} ₽\n"
                f"💳 Безнал: {shift.cashless_fact:,.2f} ₽\n"
                f"📱 QR: {shift.qr_payments:,.2f} ₽\n\n"
                f"Теперь введите данные с Z-отчета кассы:\n\n"
                f"💵 Введите НАЛИЧНЫЕ по кассе (рублей):"
            )
        else:
            await message.answer(
                f"⚠️ Смена за {shift_date.strftime('%d.%m.%Y')} не найдена в системе.\n\n"
                f"Но можно все равно проверить данные.\n\n"
                f"💵 Введите НАЛИЧНЫЕ по кассе (рублей):"
            )
            await state.update_data(
                fact_cash=0,
                fact_cashless=0,
                fact_qr=0
            )

    await state.set_state(ManualCheckStates.waiting_for_cash)


@router.message(ManualCheckStates.waiting_for_cash)
async def process_cash(message: Message, state: FSMContext):
    """Обработка наличных"""
    try:
        cash = float(message.text.replace(',', '.').replace(' ', ''))
        if cash < 0:
            raise ValueError("Сумма не может быть отрицательной")
    except ValueError:
        await message.answer("❌ Введите число (например: 15000 или 15000.50)")
        return

    await state.update_data(kkt_cash=cash)
    await message.answer("💳 Введите БЕЗНАЛИЧНЫЕ по кассе (рублей):")
    await state.set_state(ManualCheckStates.waiting_for_cashless)


@router.message(ManualCheckStates.waiting_for_cashless)
async def process_cashless(message: Message, state: FSMContext):
    """Обработка безналичных"""
    try:
        cashless = float(message.text.replace(',', '.').replace(' ', ''))
        if cashless < 0:
            raise ValueError("Сумма не может быть отрицательной")
    except ValueError:
        await message.answer("❌ Введите число (например: 8000 или 8000.50)")
        return

    await state.update_data(kkt_cashless=cashless)
    await message.answer(
        "📱 Введите QR-платежи по кассе (рублей)\n"
        "или отправьте 0, если QR нет:"
    )
    await state.set_state(ManualCheckStates.waiting_for_qr)


@router.message(ManualCheckStates.waiting_for_qr)
async def process_qr_and_show_result(message: Message, state: FSMContext):
    """Обработка QR и показ результата"""
    try:
        qr = float(message.text.replace(',', '.').replace(' ', ''))
        if qr < 0:
            raise ValueError("Сумма не может быть отрицательной")
    except ValueError:
        await message.answer("❌ Введите число (например: 3500 или 0)")
        return

    # Получить все данные
    data = await state.get_data()
    shift_date = data['shift_date']
    fact_cash = data.get('fact_cash', 0)
    fact_cashless = data.get('fact_cashless', 0)
    fact_qr = data.get('fact_qr', 0)
    kkt_cash = data['kkt_cash']
    kkt_cashless = data['kkt_cashless']
    kkt_qr = qr

    # Рассчитать расхождения
    fact_total = fact_cash + fact_cashless + fact_qr
    kkt_total = kkt_cash + kkt_cashless + kkt_qr

    diff_cash = fact_cash - kkt_cash
    diff_cashless = (fact_cashless + fact_qr) - (kkt_cashless + kkt_qr)
    diff_total = fact_total - kkt_total

    # Сформировать отчет
    report = f"""
📊 СВЕРКА СМЕНЫ С КАССОЙ
{'='*40}

📅 Дата: {shift_date.strftime('%d.%m.%Y')}

{'='*40}

💰 НАЛИЧНЫЕ:
   Факт:  {fact_cash:>12,.2f} ₽
   Касса: {kkt_cash:>12,.2f} ₽
   Разница: {diff_cash:>10,.2f} ₽

💳 БЕЗНАЛ + QR:
   Факт:  {fact_cashless + fact_qr:>12,.2f} ₽
   Касса: {kkt_cashless + kkt_qr:>12,.2f} ₽
   Разница: {diff_cashless:>10,.2f} ₽

📊 ИТОГО:
   Факт:  {fact_total:>12,.2f} ₽
   Касса: {kkt_total:>12,.2f} ₽
   Разница: {diff_total:>10,.2f} ₽

{'='*40}
"""

    # Определить статус
    tolerance = 100  # Допустимое расхождение
    issues = []

    if abs(diff_cash) > tolerance:
        issues.append(f"Наличные: {diff_cash:+,.0f} ₽")

    if abs(diff_cashless) > tolerance:
        issues.append(f"Безнал: {diff_cashless:+,.0f} ₽")

    if abs(diff_total) > tolerance:
        issues.append(f"Итого: {diff_total:+,.0f} ₽")

    if issues:
        report += "\n⚠️ РАСХОЖДЕНИЯ:\n"
        for issue in issues:
            report += f"• {issue}\n"
    else:
        report += "\n✅ Смена совпадает с кассой"

    await message.answer(report)
    await state.clear()


@router.message(Command("check_quick"))
async def quick_check_today(message: Message):
    """
    Быстрая проверка сегодняшней смены
    Только ввод итоговой суммы по кассе

    Использование: /check_quick
    """
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

        fact_total = (shift.cash_fact or 0) + (shift.cashless_fact or 0) + (shift.qr_payments or 0)

        await message.answer(
            f"📊 БЫСТРАЯ ПРОВЕРКА\n\n"
            f"📅 Сегодня: {date.today().strftime('%d.%m.%Y')}\n\n"
            f"💰 Выручка по Bot_Claude: {fact_total:,.2f} ₽\n\n"
            f"Введите ИТОГО по Z-отчету кассы (рублей):"
        )


@router.message(F.text.regexp(r'^\d+([.,]\d+)?$'))
async def quick_check_response(message: Message):
    """Обработка ответа для быстрой проверки"""
    # Проверить, не в FSM ли мы
    try:
        kkt_total = float(message.text.replace(',', '.'))
    except ValueError:
        return

    async with async_session() as session:
        result = await session.execute(
            select(Shift)
            .where(Shift.date == date.today())
            .order_by(Shift.id.desc())
        )
        shift = result.scalar_one_or_none()

        if not shift:
            return

        fact_total = (shift.cash_fact or 0) + (shift.cashless_fact or 0) + (shift.qr_payments or 0)
        diff = fact_total - kkt_total

        if abs(diff) <= 100:
            await message.answer(
                f"✅ ПРОВЕРКА ПРОЙДЕНА\n\n"
                f"📊 Факт: {fact_total:,.2f} ₽\n"
                f"🧾 Касса: {kkt_total:,.2f} ₽\n"
                f"📈 Разница: {diff:+.2f} ₽\n\n"
                f"Смена совпадает с кассой!"
            )
        else:
            await message.answer(
                f"⚠️ ОБНАРУЖЕНО РАСХОЖДЕНИЕ\n\n"
                f"📊 Факт: {fact_total:,.2f} ₽\n"
                f"🧾 Касса: {kkt_total:,.2f} ₽\n"
                f"📈 Разница: {diff:+.2f} ₽\n\n"
                f"Для детальной проверки используйте /check_manual"
            )


@router.message(Command("cancel_check"))
async def cancel_check(message: Message, state: FSMContext):
    """Отменить процесс проверки"""
    await state.clear()
    await message.answer("❌ Проверка отменена.")
