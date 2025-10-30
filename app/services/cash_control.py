"""
Контроль кассовой дисциплины
"""
from app.database import crud
from datetime import date, timedelta
from typing import Dict, List
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


async def check_cash_discipline(session: AsyncSession, date_: date) -> Dict:
    """
    Проверка кассовой дисциплины на дату

    Args:
        session: Сессия БД
        date_: Дата проверки

    Returns:
        Dict с результатами проверки
    """
    issues = []
    warnings = []

    # Получаем баланс кассы
    balance = await crud.get_cash_balance_by_date(session, date_)

    if not balance:
        issues.append("Отсутствует запись баланса кассы")
        return {
            'date': date_.isoformat(),
            'status': 'error',
            'issues': issues,
            'warnings': warnings
        }

    # Проверка 1: Расхождение между фактом и расчетом
    if balance.calculated_balance is not None:
        difference = abs(balance.closing_balance - balance.calculated_balance)
        if difference > Decimal('100'):
            issues.append(f"Расхождение баланса: {difference} руб.")

    # Проверка 2: Отрицательный баланс
    if balance.closing_balance < 0:
        issues.append(f"Отрицательный баланс кассы: {balance.closing_balance} руб.")

    # Проверка 3: Неподтвержденные транзакции
    transactions = await crud.get_transactions_by_date(session, date_, confirmed_only=False)
    unconfirmed = [t for t in transactions if not t.is_confirmed]

    if unconfirmed:
        warnings.append(f"Неподтвержденных транзакций: {len(unconfirmed)}")

    # Проверка 4: Транзакции без документов
    transactions_confirmed = [t for t in transactions if t.is_confirmed]
    no_documents = [t for t in transactions_confirmed if not t.documents and t.amount > 1000]

    if no_documents:
        warnings.append(f"Транзакций без документов (>1000 руб): {len(no_documents)}")

    # Проверка 5: Несверенный баланс
    if not balance.is_reconciled:
        warnings.append("Баланс кассы не сверен")

    status = 'error' if issues else ('warning' if warnings else 'ok')

    return {
        'date': date_.isoformat(),
        'status': status,
        'balance': float(balance.closing_balance),
        'calculated_balance': float(balance.calculated_balance) if balance.calculated_balance else None,
        'difference': float(balance.difference) if balance.difference else None,
        'is_reconciled': balance.is_reconciled,
        'unconfirmed_count': len(unconfirmed),
        'no_documents_count': len(no_documents),
        'issues': issues,
        'warnings': warnings
    }


async def get_cash_discipline_report(
    session: AsyncSession,
    start_date: date,
    end_date: date
) -> Dict:
    """
    Отчет по кассовой дисциплине за период

    Args:
        session: Сессия БД
        start_date: Начало периода
        end_date: Конец периода

    Returns:
        Dict с отчетом
    """
    results = []
    current_date = start_date

    while current_date <= end_date:
        check_result = await check_cash_discipline(session, current_date)
        results.append(check_result)
        current_date += timedelta(days=1)

    # Подсчет статистики
    total_days = len(results)
    ok_days = len([r for r in results if r['status'] == 'ok'])
    warning_days = len([r for r in results if r['status'] == 'warning'])
    error_days = len([r for r in results if r['status'] == 'error'])

    return {
        'period': f'{start_date.isoformat()} - {end_date.isoformat()}',
        'total_days': total_days,
        'ok_days': ok_days,
        'warning_days': warning_days,
        'error_days': error_days,
        'compliance_rate': (ok_days / total_days * 100) if total_days > 0 else 0,
        'daily_checks': results
    }


async def get_cash_limit_violations(
    session: AsyncSession,
    cash_limit: Decimal = Decimal('100000')
) -> List[Dict]:
    """
    Проверка превышения лимита остатка наличных в кассе

    Args:
        session: Сессия БД
        cash_limit: Лимит остатка кассы

    Returns:
        Список дат с превышением лимита
    """
    # Получаем все балансы за последние 30 дней
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    violations = []
    current_date = start_date

    while current_date <= end_date:
        balance = await crud.get_cash_balance_by_date(session, current_date)

        if balance and balance.closing_balance > cash_limit:
            violations.append({
                'date': current_date.isoformat(),
                'balance': float(balance.closing_balance),
                'limit': float(cash_limit),
                'excess': float(balance.closing_balance - cash_limit)
            })

        current_date += timedelta(days=1)

    return violations
