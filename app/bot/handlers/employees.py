"""
Обработчики для работы с сотрудниками
"""
import logging
from datetime import date, datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..filters import IsOwner, IsAdmin
from ..keyboards import get_employees_keyboard, get_employee_card_keyboard, get_contract_type_keyboard
from ...database.db import async_session
from ...database.models import Employee, Contract
from ...services.document_generator import DocumentGenerator

logger = logging.getLogger(__name__)
router = Router()


class AddEmployeeStates(StatesGroup):
    """Состояния для добавления сотрудника"""
    waiting_for_name = State()
    waiting_for_inn = State()
    waiting_for_phone = State()
    waiting_for_employment_type = State()
    waiting_for_hourly_rate = State()


@router.message(Command("employees"), IsAdmin())
async def cmd_employees(message: Message):
    """Список сотрудников"""
    async with async_session() as session:
        result = await session.execute(
            select(Employee).where(Employee.fire_date.is_(None)).order_by(Employee.full_name)
        )
        employees = result.scalars().all()

        if not employees:
            await message.answer("📋 Список сотрудников пуст")
            return

        text = "👥 *Список сотрудников:*\n\n"
        for emp in employees:
            status_emoji = "✅" if emp.is_active else "❌"
            text += f"{status_emoji} {emp.full_name}\n"
            text += f"   ID: `{emp.id}` | Тип: {emp.employment_type or 'н/д'}\n"
            if emp.hourly_rate:
                text += f"   Ставка: {emp.hourly_rate:,.2f} руб/час\n"
            text += "\n"

        text += "\n💡 Используйте /employee_<ID> для просмотра карточки"
        text += "\n➕ /add_employee - добавить сотрудника"

        await message.answer(text, parse_mode="Markdown")


@router.message(Command("add_employee"), IsAdmin())
async def cmd_add_employee(message: Message, state: FSMContext):
    """Начать добавление сотрудника"""
    await message.answer(
        "➕ *Добавление сотрудника*\n\n"
        "Введите ФИО сотрудника:",
        parse_mode="Markdown"
    )
    await state.set_state(AddEmployeeStates.waiting_for_name)


@router.message(AddEmployeeStates.waiting_for_name)
async def process_employee_name(message: Message, state: FSMContext):
    """Обработка имени сотрудника"""
    await state.update_data(full_name=message.text.strip())
    await message.answer(
        "Введите ИНН сотрудника (или /skip для пропуска):"
    )
    await state.set_state(AddEmployeeStates.waiting_for_inn)


@router.message(AddEmployeeStates.waiting_for_inn)
async def process_employee_inn(message: Message, state: FSMContext):
    """Обработка ИНН"""
    inn = None if message.text == "/skip" else message.text.strip()
    await state.update_data(inn=inn)

    await message.answer(
        "Введите телефон сотрудника (или /skip для пропуска):"
    )
    await state.set_state(AddEmployeeStates.waiting_for_phone)


@router.message(AddEmployeeStates.waiting_for_phone)
async def process_employee_phone(message: Message, state: FSMContext):
    """Обработка телефона"""
    phone = None if message.text == "/skip" else message.text.strip()
    await state.update_data(phone=phone)

    await message.answer(
        "Выберите тип трудоустройства:",
        reply_markup=get_contract_type_keyboard()
    )
    await state.set_state(AddEmployeeStates.waiting_for_employment_type)


@router.callback_query(AddEmployeeStates.waiting_for_employment_type)
async def process_employment_type(callback: CallbackQuery, state: FSMContext):
    """Обработка типа трудоустройства"""
    employment_type = callback.data.split("_")[1]
    await state.update_data(employment_type=employment_type)

    await callback.message.edit_text(
        f"Тип: {employment_type}\n\n"
        "Введите почасовую ставку в рублях (или /skip):"
    )
    await state.set_state(AddEmployeeStates.waiting_for_hourly_rate)
    await callback.answer()


@router.message(AddEmployeeStates.waiting_for_hourly_rate)
async def process_hourly_rate(message: Message, state: FSMContext):
    """Обработка ставки и создание сотрудника"""
    hourly_rate = None
    if message.text != "/skip":
        try:
            hourly_rate = float(message.text.replace(",", "."))
        except ValueError:
            await message.answer("❌ Неверный формат. Введите число:")
            return

    data = await state.get_data()

    # Создание сотрудника
    async with async_session() as session:
        employee = Employee(
            full_name=data['full_name'],
            inn=data.get('inn'),
            phone=data.get('phone'),
            employment_type=data['employment_type'],
            hourly_rate=hourly_rate,
            hire_date=date.today()
        )
        session.add(employee)
        await session.commit()
        await session.refresh(employee)

        text = (
            "✅ *Сотрудник добавлен!*\n\n"
            f"👤 {employee.full_name}\n"
            f"ID: `{employee.id}`\n"
        )
        if employee.inn:
            text += f"ИНН: {employee.inn}\n"
        if employee.phone:
            text += f"Телефон: {employee.phone}\n"
        text += f"Тип: {employee.employment_type}\n"
        if employee.hourly_rate:
            text += f"Ставка: {employee.hourly_rate:,.2f} руб/час\n"

        text += f"\n💼 Используйте /employee_{employee.id} для просмотра карточки"

        await message.answer(text, parse_mode="Markdown")

    await state.clear()


@router.message(Command(commands=["employee"]), IsAdmin())
async def cmd_employee_card(message: Message):
    """Карточка сотрудника"""
    # Парсинг ID из команды /employee_123
    try:
        employee_id = int(message.text.split("_")[1])
    except (IndexError, ValueError):
        await message.answer("❌ Неверный формат команды. Используйте: /employee_<ID>")
        return

    async with async_session() as session:
        employee = await session.get(Employee, employee_id)

        if not employee:
            await message.answer("❌ Сотрудник не найден")
            return

        # Получить контракты
        result = await session.execute(
            select(Contract).where(Contract.employee_id == employee_id).order_by(Contract.created_at.desc())
        )
        contracts = result.scalars().all()

        # Формирование карточки
        text = f"👤 *Карточка сотрудника #{employee.id}*\n\n"
        text += f"*ФИО:* {employee.full_name}\n"

        if employee.inn:
            text += f"*ИНН:* {employee.inn}\n"
        if employee.snils:
            text += f"*СНИЛС:* {employee.snils}\n"
        if employee.phone:
            text += f"*Телефон:* {employee.phone}\n"
        if employee.email:
            text += f"*Email:* {employee.email}\n"

        text += f"\n*Тип трудоустройства:* {employee.employment_type or 'н/д'}\n"
        if employee.hourly_rate:
            text += f"*Почасовая ставка:* {employee.hourly_rate:,.2f} руб/час\n"

        if employee.hire_date:
            text += f"*Дата приема:* {employee.hire_date.strftime('%d.%m.%Y')}\n"

        status = "✅ Активный" if employee.is_active else "❌ Уволен"
        text += f"*Статус:* {status}\n"

        # Договоры
        if contracts:
            text += f"\n📄 *Договоры ({len(contracts)}):*\n"
            for contract in contracts:
                active = "✅" if contract.is_active else "⏹"
                text += f"\n{active} {contract.contract_type} №{contract.contract_number or 'б/н'}\n"
                text += f"   с {contract.start_date.strftime('%d.%m.%Y')}"
                if contract.end_date:
                    text += f" по {contract.end_date.strftime('%d.%m.%Y')}"
                text += "\n"

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_employee_card_keyboard(employee_id)
        )


@router.callback_query(F.data.startswith("generate_contract_"))
async def generate_contract_callback(callback: CallbackQuery):
    """Генерация договора для сотрудника"""
    parts = callback.data.split("_")
    contract_type = parts[2]  # TD, GPH, OFFER
    employee_id = int(parts[3])

    async with async_session() as session:
        employee = await session.get(Employee, employee_id)

        if not employee:
            await callback.answer("❌ Сотрудник не найден", show_alert=True)
            return

        # Создать контракт
        contract = Contract(
            employee_id=employee_id,
            contract_type=contract_type,
            start_date=date.today(),
            position="Администратор",  # Можно сделать выбор
            salary=employee.hourly_rate * 160 if employee.hourly_rate else 30000  # 160 часов/мес
        )
        session.add(contract)
        await session.commit()
        await session.refresh(contract)

        # Генерация документа
        generator = DocumentGenerator()

        try:
            if contract_type == "TD":
                filepath = generator.generate_labor_contract(employee, contract)
            elif contract_type == "GPH":
                filepath = generator.generate_gph_contract(employee, contract)
            elif contract_type == "OFFER":
                filepath = generator.generate_offer(
                    employee,
                    employee.hourly_rate or 150.0
                )
            else:
                await callback.answer("❌ Неизвестный тип договора", show_alert=True)
                return

            # Обновить путь к файлу в БД
            contract.file_path = filepath
            await session.commit()

            await callback.message.answer(
                f"✅ Договор {contract_type} сгенерирован!\n\n"
                f"📄 Файл: {filepath}\n"
                f"Номер договора: {contract.id}\n"
            )

        except Exception as e:
            logger.error(f"Error generating contract: {e}", exc_info=True)
            await callback.answer("❌ Ошибка генерации договора", show_alert=True)

    await callback.answer()
