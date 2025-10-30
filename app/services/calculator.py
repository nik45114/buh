"""
Калькулятор налогов УСН "доходы минус расходы" 15%
"""
from app.database import crud
from datetime import date
from typing import Dict
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


async def calculate_usn_tax(
    session: AsyncSession,
    year: int,
    quarter: int = None
) -> Dict:
    """
    Расчет налога УСН "доходы минус расходы" 15%

    Args:
        session: Сессия БД
        year: Год
        quarter: Квартал (1-4), если None - весь год

    Returns:
        Dict с расчетом налога
    """
    # Определяем период
    if quarter:
        start_date = date(year, (quarter - 1) * 3 + 1, 1)
        if quarter == 4:
            end_date = date(year, 12, 31)
        else:
            # Последний день квартала
            import calendar
            last_month = quarter * 3
            last_day = calendar.monthrange(year, last_month)[1]
            end_date = date(year, last_month, last_day)
    else:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

    # Получаем транзакции
    transactions = await crud.get_transactions_by_period(
        session,
        start_date,
        end_date,
        confirmed_only=True
    )

    # Считаем доходы
    incomes = [t for t in transactions if t.type == 'income']
    total_income = sum(t.amount for t in incomes)

    # Считаем расходы (только те что учитываются в УСН)
    expenses = [
        t for t in transactions
        if t.type == 'expense'
        and t.category
        and t.category.tax_deductible
    ]
    total_expense = sum(t.amount for t in expenses)

    # База налогообложения (не может быть отрицательной)
    tax_base = max(total_income - total_expense, Decimal('0'))

    # Налог 15%
    tax_rate = Decimal('0.15')
    tax_amount = tax_base * tax_rate

    # Минимальный налог 1% от доходов
    min_tax_rate = Decimal('0.01')
    min_tax = total_income * min_tax_rate

    # К уплате = максимум из двух
    tax_to_pay = max(tax_amount, min_tax)

    logger.info(
        f"Tax calculated for {year}" + (f" Q{quarter}" if quarter else "") +
        f": income={total_income}, expense={total_expense}, tax={tax_to_pay}"
    )

    return {
        'period': f"{year} год" + (f", {quarter} квартал" if quarter else ""),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'incomes': float(total_income),
        'expenses': float(total_expense),
        'tax_base': float(tax_base),
        'tax_rate': float(tax_rate),
        'tax_amount': float(tax_amount),
        'min_tax': float(min_tax),
        'tax_to_pay': float(tax_to_pay),
        'income_count': len(incomes),
        'expense_count': len(expenses)
    }


async def calculate_quarter_taxes(session: AsyncSession, year: int) -> list[Dict]:
    """
    Расчет налога по всем кварталам года

    Args:
        session: Сессия БД
        year: Год

    Returns:
        Список расчетов по кварталам
    """
    results = []

    for quarter in range(1, 5):
        tax_data = await calculate_usn_tax(session, year, quarter)
        results.append(tax_data)

    return results


def calculate_advance_payments(quarter_taxes: list[Dict]) -> Dict:
    """
    Расчет авансовых платежей по кварталам

    Args:
        quarter_taxes: Список расчетов налога по кварталам

    Returns:
        Dict с авансовыми платежами
    """
    payments = {}
    cumulative_tax = Decimal('0')
    paid_advances = Decimal('0')

    for i, quarter_data in enumerate(quarter_taxes, start=1):
        quarter_tax = Decimal(str(quarter_data['tax_to_pay']))
        cumulative_tax = quarter_tax

        # Авансовый платеж = налог нарастающим итогом - уже уплаченные авансы
        advance_payment = cumulative_tax - paid_advances

        payments[f'Q{i}'] = {
            'quarter': i,
            'cumulative_income': quarter_data['incomes'],
            'cumulative_expense': quarter_data['expenses'],
            'cumulative_tax': float(cumulative_tax),
            'advance_payment': float(max(advance_payment, Decimal('0'))),
            'payment_deadline': get_payment_deadline(int(quarter_data['start_date'][:4]), i)
        }

        paid_advances += max(advance_payment, Decimal('0'))

    return payments


def get_payment_deadline(year: int, quarter: int) -> str:
    """
    Получить срок уплаты авансового платежа

    Args:
        year: Год
        quarter: Квартал

    Returns:
        Дата в формате YYYY-MM-DD
    """
    deadlines = {
        1: f"{year}-04-25",  # До 25 апреля
        2: f"{year}-07-25",  # До 25 июля
        3: f"{year}-10-25",  # До 25 октября
        4: f"{year + 1}-03-31"  # До 31 марта следующего года (годовая декларация)
    }
    return deadlines.get(quarter, "")


async def get_tax_summary(session: AsyncSession, year: int) -> Dict:
    """
    Полная сводка по налогам за год

    Args:
        session: Сессия БД
        year: Год

    Returns:
        Dict с полной информацией по налогам
    """
    # Получаем расчеты по кварталам
    quarter_taxes = await calculate_quarter_taxes(session, year)

    # Расчет авансовых платежей
    advance_payments = calculate_advance_payments(quarter_taxes)

    # Годовой итог
    annual = quarter_taxes[-1] if quarter_taxes else {}

    return {
        'year': year,
        'tax_system': 'УСН "доходы минус расходы" 15%',
        'company': {
            'name': 'ООО "Лепта"',
            'inn': '6829164121'
        },
        'annual_summary': annual,
        'quarterly_data': quarter_taxes,
        'advance_payments': advance_payments,
        'total_tax_to_pay': annual.get('tax_to_pay', 0)
    }
