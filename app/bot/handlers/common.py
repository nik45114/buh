"""
Общие команды бота
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.bot.keyboards import get_main_menu_keyboard, get_reports_keyboard
from app.database.db import async_session_maker
from app.database import crud
from datetime import datetime

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    async with async_session_maker() as session:
        # Создаем или получаем пользователя
        await crud.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "🏢 Бухгалтерский бот для ООО \"Лепта\"\n"
        "📊 УСН \"доходы минус расходы\" 15%\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help"""
    help_text = """
📖 <b>Справка по командам:</b>

<b>Основные команды:</b>
/start - Главное меню
/balance - Баланс кассы
/today - Операции за сегодня
/add - Быстрое добавление транзакции

<b>Отчеты:</b>
/week - Отчет за неделю
/month - Отчет за месяц
/tax - Расчет налога
/kudir - Генерация КУДиР

<b>Добавление данных:</b>
• Отправьте фото чека для автоматического распознавания
• Используйте команды для ручного ввода

<b>Поддержка:</b>
По вопросам обращайтесь к администратору
"""
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей операции"""
    await state.clear()
    await message.answer(
        "❌ Операция отменена",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "🏠 Главное меню\n\nВыберите действие:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "reports")
async def callback_reports(callback: CallbackQuery):
    """Меню отчетов"""
    await callback.message.edit_text(
        "📊 Отчеты\n\nВыберите период:",
        reply_markup=get_reports_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена через callback"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Операция отменена",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.message(Command("balance"))
@router.callback_query(F.data == "balance")
async def show_balance(event: Message | CallbackQuery):
    """Показать баланс кассы"""
    async with async_session_maker() as session:
        balance = await crud.get_current_cash_balance(session)

    text = (
        f"💰 <b>Баланс кассы на {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
        f"Фактический: <b>{balance.closing_balance:,.2f} ₽</b>\n"
        f"Расчетный: {balance.calculated_balance:,.2f} ₽\n"
    )

    if balance.calculated_balance:
        diff = balance.closing_balance - balance.calculated_balance
        if abs(diff) < 100:
            text += f"\n✅ Сходится (разница: {abs(diff):.2f} ₽)"
        else:
            text += f"\n⚠️ Расхождение: {diff:,.2f} ₽"

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML")
    else:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        await event.answer()


@router.message(Command("today"))
@router.callback_query(F.data == "today")
async def show_today(event: Message | CallbackQuery):
    """Показать операции за сегодня"""
    today = datetime.now().date()

    async with async_session_maker() as session:
        transactions = await crud.get_transactions_by_date(session, today)

    incomes = [t for t in transactions if t.type == 'income']
    expenses = [t for t in transactions if t.type == 'expense']

    total_income = sum(t.amount for t in incomes)
    total_expense = sum(t.amount for t in expenses)

    text = f"📅 <b>Операции за {today.strftime('%d.%m.%Y')}</b>\n\n"

    if incomes:
        text += "💰 <b>Доходы:</b>\n"
        for t in incomes:
            status = "✅" if t.is_confirmed else "⏳"
            text += f"  {status} {t.amount:,.0f} ₽ - {t.counterparty or 'Без контрагента'}\n"
        text += f"<b>Итого:</b> {total_income:,.2f} ₽\n\n"
    else:
        text += "💰 <b>Доходов нет</b>\n\n"

    if expenses:
        text += "💸 <b>Расходы:</b>\n"
        for t in expenses:
            status = "✅" if t.is_confirmed else "⏳"
            desc = t.description or (t.category.name if t.category else 'Без категории')
            text += f"  {status} {t.amount:,.0f} ₽ - {desc}\n"
        text += f"<b>Итого:</b> {total_expense:,.2f} ₽\n\n"
    else:
        text += "💸 <b>Расходов нет</b>\n\n"

    text += f"📊 <b>Баланс дня:</b> {total_income - total_expense:,.2f} ₽"

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML")
    else:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        await event.answer()
