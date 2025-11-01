"""
Команды для администраторов
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.bot.filters import IsAdmin
from app.bot.states import AddExpenseStates
from app.bot.keyboards import get_category_keyboard, get_payment_method_keyboard
from app.database.db import async_session_maker
from app.database import crud
from datetime import datetime
from decimal import Decimal
import logging

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

logger = logging.getLogger(__name__)


@router.message(Command("add_expense"))
@router.callback_query(F.data == "add_expense")
async def cmd_add_expense(event: Message | CallbackQuery, state: FSMContext):
    """Начать добавление расхода"""
    text = "💸 <b>Добавление расхода</b>\n\nВведите сумму (в рублях):"

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML")
    else:
        await event.message.edit_text(text, parse_mode="HTML")
        await event.answer()

    await state.set_state(AddExpenseStates.waiting_for_amount)


@router.message(AddExpenseStates.waiting_for_amount)
async def process_expense_amount(message: Message, state: FSMContext):
    """Обработка суммы расхода"""
    try:
        # Парсим сумму
        amount_str = message.text.replace(',', '.').replace(' ', '')
        amount = Decimal(amount_str)

        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Попробуйте еще раз:")
            return

        await state.update_data(amount=amount)

        # Запрашиваем категорию
        async with async_session_maker() as session:
            categories = await crud.get_categories(session, type_='expense', active_only=True)

        await message.answer(
            f"✅ Сумма: <b>{amount:,.2f} ₽</b>\n\n"
            "Выберите категорию:",
            parse_mode="HTML",
            reply_markup=get_category_keyboard(categories, 'expense')
        )

        await state.set_state(AddExpenseStates.waiting_for_category)

    except (ValueError, decimal.InvalidOperation):
        await message.answer("❌ Неверный формат суммы. Введите число (например: 1000 или 1500.50):")


@router.callback_query(F.data.startswith("category:expense:"), AddExpenseStates.waiting_for_category)
async def process_expense_category(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора категории"""
    category_id = int(callback.data.split(':')[2])

    async with async_session_maker() as session:
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalars().first()

    await state.update_data(category_id=category_id, category_name=category.name if category else None)

    await callback.message.edit_text(
        f"✅ Категория: <b>{category.name if category else 'Не выбрана'}</b>\n\n"
        "Введите контрагента (поставщика) или отправьте '-' чтобы пропустить:",
        parse_mode="HTML"
    )

    await state.set_state(AddExpenseStates.waiting_for_counterparty)
    await callback.answer()


@router.message(AddExpenseStates.waiting_for_counterparty)
async def process_expense_counterparty(message: Message, state: FSMContext):
    """Обработка контрагента"""
    counterparty = None if message.text == '-' else message.text

    await state.update_data(counterparty=counterparty)

    await message.answer(
        "Введите описание расхода или отправьте '-' чтобы пропустить:"
    )

    await state.set_state(AddExpenseStates.waiting_for_description)


@router.message(AddExpenseStates.waiting_for_description)
async def process_expense_description(message: Message, state: FSMContext):
    """Обработка описания"""
    description = None if message.text == '-' else message.text

    await state.update_data(description=description)

    await message.answer(
        "Выберите способ оплаты:",
        reply_markup=get_payment_method_keyboard()
    )

    await state.set_state(AddExpenseStates.waiting_for_payment_method)


@router.callback_query(F.data.startswith("payment:"), AddExpenseStates.waiting_for_payment_method)
async def process_expense_payment_method(callback: CallbackQuery, state: FSMContext):
    """Обработка способа оплаты"""
    payment_method = callback.data.split(':')[1]
    payment_methods = {
        'cash': 'Наличные',
        'cashless': 'Безналичные',
        'card': 'Карта',
        'qr': 'QR-код'
    }

    await state.update_data(payment_method=payment_method)

    # Получаем все данные
    data = await state.get_data()

    # Создаем транзакцию
    async with async_session_maker() as session:
        user = await crud.get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name
        )

        transaction_data = {
            'date': datetime.now().date(),
            'type': 'expense',
            'amount': data['amount'],
            'category_id': data.get('category_id'),
            'counterparty': data.get('counterparty'),
            'description': data.get('description'),
            'payment_method': payment_method,
            'source': 'manual',
            'is_confirmed': True,  # Админы могут сразу подтверждать
            'created_by': user.id,
            'confirmed_by': user.id,
            'confirmed_at': datetime.now()
        }

        transaction = await crud.create_transaction(session, transaction_data)

    # Формируем сообщение об успехе
    text = (
        f"✅ <b>Расход добавлен</b>\n\n"
        f"💰 Сумма: <b>{data['amount']:,.2f} ₽</b>\n"
        f"📂 Категория: {data.get('category_name', 'Не указана')}\n"
    )

    if data.get('counterparty'):
        text += f"🏪 Контрагент: {data['counterparty']}\n"

    if data.get('description'):
        text += f"📝 Описание: {data['description']}\n"

    text += f"💳 Оплата: {payment_methods.get(payment_method, payment_method)}\n"
    text += f"📅 Дата: {datetime.now().strftime('%d.%m.%Y')}\n"
    text += f"\n№ транзакции: {transaction.id}"

    await callback.message.edit_text(text, parse_mode="HTML")
    await state.clear()
    await callback.answer("✅ Расход добавлен")


@router.message(Command("confirm"))
async def cmd_confirm_transactions(message: Message):
    """Показать неподтвержденные транзакции"""
    async with async_session_maker() as session:
        # Получаем все неподтвержденные транзакции
        from sqlalchemy import select
        from app.database.models import Transaction

        result = await session.execute(
            select(Transaction)
            .where(Transaction.is_confirmed == False)
            .order_by(Transaction.created_at.desc())
            .limit(10)
        )
        transactions = result.scalars().all()

    if not transactions:
        await message.answer("✅ Нет транзакций, ожидающих подтверждения")
        return

    text = "⏳ <b>Неподтвержденные транзакции:</b>\n\n"

    for t in transactions:
        type_emoji = "💰" if t.type == 'income' else "💸"
        text += (
            f"{type_emoji} <b>{t.amount:,.2f} ₽</b>\n"
            f"📅 {t.date.strftime('%d.%m.%Y')}\n"
        )

        if t.category:
            text += f"📂 {t.category.name}\n"

        if t.counterparty:
            text += f"🏪 {t.counterparty}\n"

        if t.description:
            text += f"📝 {t.description}\n"

        text += f"ID: {t.id}\n"
        text += f"───────────\n\n"

    text += "\nИспользуйте /confirm_id <id> для подтверждения"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("confirm_id"))
async def cmd_confirm_transaction_by_id(message: Message):
    """Подтвердить транзакцию по ID"""
    try:
        # Извлекаем ID из команды
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Использование: /confirm_id <id>")
            return

        transaction_id = int(parts[1])

        async with async_session_maker() as session:
            user = await crud.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name
            )

            transaction = await crud.confirm_transaction(session, transaction_id, user.id)

        await message.answer(
            f"✅ Транзакция #{transaction_id} подтверждена\n"
            f"💰 Сумма: {transaction.amount:,.2f} ₽"
        )

    except ValueError:
        await message.answer("❌ Неверный ID транзакции")
    except Exception as e:
        logger.error(f"Error confirming transaction: {e}")
        await message.answer(f"❌ Ошибка при подтверждении: {str(e)}")


# Добавляем импорт для category
from sqlalchemy import select
from app.database.models import Category
import decimal
