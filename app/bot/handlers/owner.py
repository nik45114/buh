"""
Команды для владельца (расширенные права)
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from app.bot.filters import IsOwner
from app.database.db import async_session_maker
from app.database import crud
from app.services.calculator import calculate_usn_tax, get_tax_summary
from app.services.kudir_generator import generate_kudir_file
from app.services.cash_control import check_cash_discipline, get_cash_discipline_report
from datetime import datetime, date, timedelta
import logging

router = Router()
router.message.filter(IsOwner())
router.callback_query.filter(IsOwner())

logger = logging.getLogger(__name__)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика"""
    today = date.today()
    month_start = date(today.year, today.month, 1)

    async with async_session_maker() as session:
        # Статистика за месяц
        stats = await crud.get_period_statistics(session, month_start, today)

        # Балансы кассы
        balance = await crud.get_current_cash_balance(session)

    text = (
        f"📊 <b>Статистика за {today.strftime('%B %Y')}</b>\n\n"
        f"💰 Доходы: <b>{stats['total_income']:,.2f} ₽</b>\n"
        f"   Операций: {stats['income_count']}\n\n"
        f"💸 Расходы: <b>{stats['total_expense']:,.2f} ₽</b>\n"
        f"   Операций: {stats['expense_count']}\n"
        f"   Учитываемые в УСН: {stats['deductible_expense']:,.2f} ₽\n\n"
        f"📈 Прибыль: <b>{stats['balance']:,.2f} ₽</b>\n\n"
        f"💵 <b>Касса сегодня:</b>\n"
        f"   Фактически: {balance.closing_balance:,.2f} ₽\n"
        f"   Расчетно: {balance.calculated_balance:,.2f} ₽\n"
    )

    if balance.calculated_balance:
        diff = balance.closing_balance - balance.calculated_balance
        if abs(diff) < 100:
            text += f"   ✅ Сходится\n"
        else:
            text += f"   ⚠️ Расхождение: {diff:,.2f} ₽\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("tax"))
@router.callback_query(F.data == "report:tax")
async def cmd_tax(event: Message | CallbackQuery):
    """Расчет налога УСН 15%"""
    year = datetime.now().year
    quarter = (datetime.now().month - 1) // 3 + 1

    async with async_session_maker() as session:
        tax_data = await calculate_usn_tax(session, year, quarter)

    text = (
        f"💼 <b>Расчет налога УСН 15%</b>\n"
        f"📅 {year} год, {quarter} квартал\n\n"
        f"💰 Доходы: <b>{tax_data['incomes']:,.2f} ₽</b>\n"
        f"💸 Расходы: <b>{tax_data['expenses']:,.2f} ₽</b>\n"
        f"   (учитываемые в УСН)\n\n"
        f"➖ База налогообложения:\n"
        f"   <b>{tax_data['tax_base']:,.2f} ₽</b>\n\n"
        f"📊 Налог 15%: {tax_data['tax_amount']:,.2f} ₽\n"
        f"⚠️ Минимальный налог 1%: {tax_data['min_tax']:,.2f} ₽\n\n"
        f"💳 <b>К уплате: {tax_data['tax_to_pay']:,.2f} ₽</b>\n\n"
        f"📌 Срок уплаты: 25 число следующего месяца"
    )

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML")
    else:
        await event.message.edit_text(text, parse_mode="HTML")
        await event.answer()


@router.message(Command("kudir"))
@router.callback_query(F.data == "report:kudir")
async def cmd_kudir(event: Message | CallbackQuery):
    """Генерация КУДиР"""
    message = event if isinstance(event, Message) else event.message

    await message.answer("⏳ Генерирую КУДиР...")

    try:
        year = datetime.now().year

        async with async_session_maker() as session:
            filepath = await generate_kudir_file(session, year)

        document = FSInputFile(filepath)

        await message.answer_document(
            document,
            caption=f"📊 КУДиР за {year} год\n\nООО \"Лепта\""
        )

        if isinstance(event, CallbackQuery):
            await event.answer("✅ КУДиР сгенерирована")

    except Exception as e:
        logger.error(f"Error generating KUDiR: {e}")
        await message.answer(f"❌ Ошибка при генерации КУДиР: {str(e)}")


@router.message(Command("week"))
@router.callback_query(F.data == "report:week")
async def cmd_week(event: Message | CallbackQuery):
    """Отчет за неделю"""
    today = date.today()
    week_ago = today - timedelta(days=7)

    async with async_session_maker() as session:
        stats = await crud.get_period_statistics(session, week_ago, today)

    text = (
        f"📅 <b>Отчет за неделю</b>\n"
        f"{week_ago.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}\n\n"
        f"💰 Доходы: <b>{stats['total_income']:,.2f} ₽</b>\n"
        f"   Операций: {stats['income_count']}\n\n"
        f"💸 Расходы: <b>{stats['total_expense']:,.2f} ₽</b>\n"
        f"   Операций: {stats['expense_count']}\n\n"
        f"📈 Баланс: <b>{stats['balance']:,.2f} ₽</b>"
    )

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML")
    else:
        await event.message.edit_text(text, parse_mode="HTML")
        await event.answer()


@router.message(Command("month"))
@router.callback_query(F.data == "report:month")
async def cmd_month(event: Message | CallbackQuery):
    """Отчет за месяц"""
    today = date.today()
    month_start = date(today.year, today.month, 1)

    async with async_session_maker() as session:
        stats = await crud.get_period_statistics(session, month_start, today)

    text = (
        f"📅 <b>Отчет за {today.strftime('%B %Y')}</b>\n\n"
        f"💰 Доходы: <b>{stats['total_income']:,.2f} ₽</b>\n"
        f"   Операций: {stats['income_count']}\n\n"
        f"💸 Расходы: <b>{stats['total_expense']:,.2f} ₽</b>\n"
        f"   Операций: {stats['expense_count']}\n"
        f"   Учитываемые в УСН: {stats['deductible_expense']:,.2f} ₽\n\n"
        f"📈 Прибыль: <b>{stats['balance']:,.2f} ₽</b>\n\n"
        f"💼 База для налога: {stats['total_income'] - stats['deductible_expense']:,.2f} ₽\n"
        f"💳 Налог 15%: {(stats['total_income'] - stats['deductible_expense']) * 0.15:,.2f} ₽"
    )

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML")
    else:
        await event.message.edit_text(text, parse_mode="HTML")
        await event.answer()


@router.message(Command("quarter"))
@router.callback_query(F.data == "report:quarter")
async def cmd_quarter(event: Message | CallbackQuery):
    """Отчет за квартал"""
    today = date.today()
    quarter = (today.month - 1) // 3 + 1
    quarter_start = date(today.year, (quarter - 1) * 3 + 1, 1)

    async with async_session_maker() as session:
        stats = await crud.get_period_statistics(session, quarter_start, today)
        tax_data = await calculate_usn_tax(session, today.year, quarter)

    text = (
        f"📅 <b>Отчет за {quarter} квартал {today.year}</b>\n\n"
        f"💰 Доходы: <b>{stats['total_income']:,.2f} ₽</b>\n"
        f"   Операций: {stats['income_count']}\n\n"
        f"💸 Расходы: <b>{stats['total_expense']:,.2f} ₽</b>\n"
        f"   Операций: {stats['expense_count']}\n"
        f"   Учитываемые в УСН: {stats['deductible_expense']:,.2f} ₽\n\n"
        f"📈 Прибыль: <b>{stats['balance']:,.2f} ₽</b>\n\n"
        f"💼 <b>Налоги:</b>\n"
        f"   База: {tax_data['tax_base']:,.2f} ₽\n"
        f"   Налог 15%: {tax_data['tax_amount']:,.2f} ₽\n"
        f"   Минимальный 1%: {tax_data['min_tax']:,.2f} ₽\n"
        f"   <b>К уплате: {tax_data['tax_to_pay']:,.2f} ₽</b>"
    )

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML")
    else:
        await event.message.edit_text(text, parse_mode="HTML")
        await event.answer()


@router.message(Command("check_cash"))
async def cmd_check_cash(message: Message):
    """Проверка кассовой дисциплины"""
    today = date.today()

    async with async_session_maker() as session:
        check_result = await check_cash_discipline(session, today)

    text = f"🔍 <b>Проверка кассовой дисциплины</b>\n📅 {today.strftime('%d.%m.%Y')}\n\n"

    if check_result['status'] == 'ok':
        text += "✅ <b>Все в порядке</b>\n\n"
    elif check_result['status'] == 'warning':
        text += "⚠️ <b>Есть предупреждения</b>\n\n"
    else:
        text += "❌ <b>Обнаружены проблемы</b>\n\n"

    text += f"💰 Баланс: {check_result['balance']:,.2f} ₽\n"
    if check_result['calculated_balance']:
        text += f"💵 Расчетный: {check_result['calculated_balance']:,.2f} ₽\n"

    if check_result['issues']:
        text += "\n<b>Проблемы:</b>\n"
        for issue in check_result['issues']:
            text += f"❌ {issue}\n"

    if check_result['warnings']:
        text += "\n<b>Предупреждения:</b>\n"
        for warning in check_result['warnings']:
            text += f"⚠️ {warning}\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("year_summary"))
async def cmd_year_summary(message: Message):
    """Годовая сводка"""
    year = datetime.now().year

    await message.answer(f"⏳ Формирую годовую сводку за {year}...")

    try:
        async with async_session_maker() as session:
            summary = await get_tax_summary(session, year)

        text = (
            f"📊 <b>Годовая сводка {year}</b>\n\n"
            f"🏢 {summary['company']['name']}\n"
            f"🔢 ИНН: {summary['company']['inn']}\n"
            f"📋 {summary['tax_system']}\n\n"
            f"<b>Итоги года:</b>\n"
            f"💰 Доходы: <b>{summary['annual_summary']['incomes']:,.2f} ₽</b>\n"
            f"💸 Расходы: <b>{summary['annual_summary']['expenses']:,.2f} ₽</b>\n"
            f"📈 База: <b>{summary['annual_summary']['tax_base']:,.2f} ₽</b>\n\n"
            f"💼 <b>Налог к уплате: {summary['total_tax_to_pay']:,.2f} ₽</b>\n\n"
        )

        # Добавляем информацию по кварталам
        text += "<b>По кварталам:</b>\n"
        for i, q_data in enumerate(summary['quarterly_data'], 1):
            text += (
                f"\n{i} квартал:\n"
                f"  Доходы: {q_data['incomes']:,.0f} ₽\n"
                f"  Расходы: {q_data['expenses']:,.0f} ₽\n"
                f"  Налог: {q_data['tax_to_pay']:,.0f} ₽\n"
            )

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating year summary: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
