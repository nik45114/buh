"""
FSM состояния для Telegram бота
"""
from aiogram.fsm.state import State, StatesGroup


class AddIncomeStates(StatesGroup):
    """Состояния добавления дохода"""
    waiting_for_amount = State()
    waiting_for_counterparty = State()
    waiting_for_description = State()
    waiting_for_date = State()


class AddExpenseStates(StatesGroup):
    """Состояния добавления расхода"""
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_counterparty = State()
    waiting_for_description = State()
    waiting_for_date = State()
    waiting_for_payment_method = State()


class EditTransactionStates(StatesGroup):
    """Состояния редактирования транзакции"""
    waiting_for_field = State()
    waiting_for_value = State()
