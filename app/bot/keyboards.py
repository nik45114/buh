"""
Клавиатуры для Telegram бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Dict, List


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💰 Добавить доход", callback_data="add_income"),
        InlineKeyboardButton(text="💸 Добавить расход", callback_data="add_expense")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Баланс кассы", callback_data="balance"),
        InlineKeyboardButton(text="📅 Сегодня", callback_data="today")
    )
    builder.row(
        InlineKeyboardButton(text="📈 Отчеты", callback_data="reports"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
    )

    return builder.as_markup()


def get_receipt_confirmation_keyboard(receipt_data: Dict) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения чека"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_receipt:{receipt_data.get('amount')}"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_receipt")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_receipt")
    )

    return builder.as_markup()


def get_category_keyboard(categories: List, type_: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора категории"""
    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.row(
            InlineKeyboardButton(
                text=category.name,
                callback_data=f"category:{type_}:{category.id}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )

    return builder.as_markup()


def get_payment_method_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора способа оплаты"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💵 Наличные", callback_data="payment:cash"),
        InlineKeyboardButton(text="💳 Безнал", callback_data="payment:cashless")
    )
    builder.row(
        InlineKeyboardButton(text="💳 Карта", callback_data="payment:card"),
        InlineKeyboardButton(text="📱 QR", callback_data="payment:qr")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )

    return builder.as_markup()


def get_reports_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отчетов"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📅 За сегодня", callback_data="report:today"),
        InlineKeyboardButton(text="📅 За неделю", callback_data="report:week")
    )
    builder.row(
        InlineKeyboardButton(text="📅 За месяц", callback_data="report:month"),
        InlineKeyboardButton(text="📅 За квартал", callback_data="report:quarter")
    )
    builder.row(
        InlineKeyboardButton(text="📊 КУДиР", callback_data="report:kudir"),
        InlineKeyboardButton(text="💼 Налоги", callback_data="report:tax")
    )
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data="main_menu")
    )

    return builder.as_markup()


def get_confirmation_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"{action}:yes:{item_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"{action}:no:{item_id}")
    )

    return builder.as_markup()


def get_transaction_actions_keyboard(transaction_id: int, is_confirmed: bool) -> InlineKeyboardMarkup:
    """Клавиатура действий с транзакцией"""
    builder = InlineKeyboardBuilder()

    if not is_confirmed:
        builder.row(
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_transaction:{transaction_id}")
        )

    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_transaction:{transaction_id}"),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_transaction:{transaction_id}")
    )

    return builder.as_markup()


def get_employees_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для работы с сотрудниками"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="➕ Добавить", callback_data="add_employee")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список", callback_data="list_employees")
    )

    return builder.as_markup()


def get_employee_card_keyboard(employee_id: int) -> InlineKeyboardMarkup:
    """Клавиатура карточки сотрудника"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📝 Трудовой договор", callback_data=f"generate_contract_TD_{employee_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📄 Договор ГПХ", callback_data=f"generate_contract_GPH_{employee_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📃 Оферта", callback_data=f"generate_contract_OFFER_{employee_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_employee_{employee_id}"),
        InlineKeyboardButton(text="🗑️ Уволить", callback_data=f"fire_employee_{employee_id}")
    )

    return builder.as_markup()


def get_contract_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа договора"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="Трудовой договор (ТД)", callback_data="employment_TD")
    )
    builder.row(
        InlineKeyboardButton(text="Гражданско-правовой (ГПХ)", callback_data="employment_GPH")
    )
    builder.row(
        InlineKeyboardButton(text="Оферта", callback_data="employment_OFFER")
    )
    builder.row(
        InlineKeyboardButton(text="Самозанятый", callback_data="employment_SELF_EMPLOYED")
    )

    return builder.as_markup()
