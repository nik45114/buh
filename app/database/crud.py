"""
CRUD операции для работы с базой данных
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload
from app.database.models import (
    User, Category, Transaction, Document,
    CashBalance, ShiftReport, Setting, AuditLog
)
from datetime import date, datetime
from typing import List, Optional, Dict
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════
# USERS
# ═══════════════════════════════════════════════════

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None
) -> User:
    """Получить или создать пользователя"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalars().first()

    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            role='user'
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Created new user: {telegram_id}")

    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Получить пользователя по Telegram ID"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalars().first()


# ═══════════════════════════════════════════════════
# CATEGORIES
# ═══════════════════════════════════════════════════

async def get_categories(
    session: AsyncSession,
    type_: Optional[str] = None,
    active_only: bool = True
) -> List[Category]:
    """Получить список категорий"""
    query = select(Category)

    if type_:
        query = query.where(Category.type == type_)
    if active_only:
        query = query.where(Category.is_active == True)

    query = query.order_by(Category.sort_order)

    result = await session.execute(query)
    return result.scalars().all()


async def get_category_by_name(session: AsyncSession, name: str) -> Optional[Category]:
    """Получить категорию по имени"""
    result = await session.execute(
        select(Category).where(Category.name == name)
    )
    return result.scalars().first()


# ═══════════════════════════════════════════════════
# TRANSACTIONS
# ═══════════════════════════════════════════════════

async def create_transaction(session: AsyncSession, data: Dict) -> Transaction:
    """Создать транзакцию"""
    transaction = Transaction(**data)
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    logger.info(f"Created transaction: {transaction.id}, type: {transaction.type}, amount: {transaction.amount}")
    return transaction


async def get_transaction_by_id(session: AsyncSession, transaction_id: int) -> Optional[Transaction]:
    """Получить транзакцию по ID"""
    result = await session.execute(
        select(Transaction)
        .options(selectinload(Transaction.category))
        .where(Transaction.id == transaction_id)
    )
    return result.scalars().first()


async def get_transactions_by_date(
    session: AsyncSession,
    date_: date,
    confirmed_only: bool = False
) -> List[Transaction]:
    """Получить транзакции за дату"""
    query = select(Transaction).where(Transaction.date == date_)

    if confirmed_only:
        query = query.where(Transaction.is_confirmed == True)

    query = query.options(selectinload(Transaction.category))
    query = query.order_by(Transaction.created_at)

    result = await session.execute(query)
    return result.scalars().all()


async def get_transactions_by_period(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    confirmed_only: bool = False,
    type_: Optional[str] = None
) -> List[Transaction]:
    """Получить транзакции за период"""
    query = select(Transaction).where(
        and_(
            Transaction.date >= start_date,
            Transaction.date <= end_date
        )
    )

    if confirmed_only:
        query = query.where(Transaction.is_confirmed == True)

    if type_:
        query = query.where(Transaction.type == type_)

    query = query.options(selectinload(Transaction.category))
    query = query.order_by(Transaction.date, Transaction.created_at)

    result = await session.execute(query)
    return result.scalars().all()


async def confirm_transaction(
    session: AsyncSession,
    transaction_id: int,
    user_id: int
) -> Transaction:
    """Подтвердить транзакцию"""
    transaction = await get_transaction_by_id(session, transaction_id)
    if not transaction:
        raise ValueError(f"Transaction {transaction_id} not found")

    transaction.is_confirmed = True
    transaction.confirmed_at = datetime.now()
    transaction.confirmed_by = user_id

    await session.commit()
    await session.refresh(transaction)
    logger.info(f"Transaction {transaction_id} confirmed by user {user_id}")
    return transaction


async def delete_transaction(session: AsyncSession, transaction_id: int) -> bool:
    """Удалить транзакцию"""
    transaction = await get_transaction_by_id(session, transaction_id)
    if not transaction:
        return False

    await session.delete(transaction)
    await session.commit()
    logger.info(f"Transaction {transaction_id} deleted")
    return True


# ═══════════════════════════════════════════════════
# CASH BALANCE
# ═══════════════════════════════════════════════════

async def get_cash_balance_by_date(session: AsyncSession, date_: date) -> Optional[CashBalance]:
    """Получить баланс кассы на дату"""
    result = await session.execute(
        select(CashBalance).where(CashBalance.date == date_)
    )
    return result.scalars().first()


async def get_current_cash_balance(session: AsyncSession) -> CashBalance:
    """Получить текущий баланс кассы"""
    today = date.today()
    balance = await get_cash_balance_by_date(session, today)

    if not balance:
        # Создаем новую запись
        # Рассчитываем баланс на основе транзакций
        calculated = await calculate_cash_balance(session, today)

        balance = CashBalance(
            date=today,
            opening_balance=Decimal('0'),
            closing_balance=calculated,
            calculated_balance=calculated
        )
        session.add(balance)
        await session.commit()
        await session.refresh(balance)

    return balance


async def calculate_cash_balance(session: AsyncSession, date_: date) -> Decimal:
    """Рассчитать баланс кассы на дату"""
    # Получаем все подтвержденные транзакции до даты включительно
    result = await session.execute(
        select(Transaction).where(
            and_(
                Transaction.date <= date_,
                Transaction.is_confirmed == True,
                Transaction.payment_method == 'cash'
            )
        )
    )
    transactions = result.scalars().all()

    balance = Decimal('0')
    for t in transactions:
        if t.type == 'income':
            balance += t.amount
        else:
            balance -= t.amount

    return balance


async def update_cash_balance(
    session: AsyncSession,
    date_: date,
    closing_balance: Decimal,
    notes: Optional[str] = None
) -> CashBalance:
    """Обновить баланс кассы"""
    balance = await get_cash_balance_by_date(session, date_)

    calculated = await calculate_cash_balance(session, date_)

    if balance:
        balance.closing_balance = closing_balance
        balance.calculated_balance = calculated
        if notes:
            balance.notes = notes
    else:
        balance = CashBalance(
            date=date_,
            closing_balance=closing_balance,
            calculated_balance=calculated,
            notes=notes
        )
        session.add(balance)

    await session.commit()
    await session.refresh(balance)
    return balance


# ═══════════════════════════════════════════════════
# SHIFT REPORTS
# ═══════════════════════════════════════════════════

async def create_shift_report(session: AsyncSession, data: Dict) -> ShiftReport:
    """Создать отчет о смене"""
    report = ShiftReport(**data)
    session.add(report)
    await session.commit()
    await session.refresh(report)
    logger.info(f"Created shift report: {report.date} {report.shift}")
    return report


async def get_unprocessed_shift_reports(session: AsyncSession) -> List[ShiftReport]:
    """Получить необработанные отчеты о сменах"""
    result = await session.execute(
        select(ShiftReport)
        .where(ShiftReport.processed == False)
        .order_by(ShiftReport.date)
    )
    return result.scalars().all()


async def mark_shift_report_processed(session: AsyncSession, report_id: int) -> ShiftReport:
    """Отметить отчет как обработанный"""
    result = await session.execute(
        select(ShiftReport).where(ShiftReport.id == report_id)
    )
    report = result.scalars().first()

    if report:
        report.processed = True
        report.processed_at = datetime.now()
        await session.commit()
        await session.refresh(report)

    return report


# ═══════════════════════════════════════════════════
# DOCUMENTS
# ═══════════════════════════════════════════════════

async def create_document(session: AsyncSession, data: Dict) -> Document:
    """Создать документ"""
    document = Document(**data)
    session.add(document)
    await session.commit()
    await session.refresh(document)
    logger.info(f"Created document: {document.id}, type: {document.file_type}")
    return document


# ═══════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════

async def create_audit_log(session: AsyncSession, data: Dict) -> AuditLog:
    """Создать запись в логе аудита"""
    log_entry = AuditLog(**data)
    session.add(log_entry)
    await session.commit()
    return log_entry


# ═══════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════

async def get_period_statistics(
    session: AsyncSession,
    start_date: date,
    end_date: date
) -> Dict:
    """Получить статистику за период"""
    transactions = await get_transactions_by_period(
        session, start_date, end_date, confirmed_only=True
    )

    incomes = [t for t in transactions if t.type == 'income']
    expenses = [t for t in transactions if t.type == 'expense']

    # Расходы с учетом налогообложения
    deductible_expenses = [
        t for t in expenses
        if t.category and t.category.tax_deductible
    ]

    total_income = sum(t.amount for t in incomes)
    total_expense = sum(t.amount for t in expenses)
    deductible_expense = sum(t.amount for t in deductible_expenses)

    return {
        'period': f'{start_date} - {end_date}',
        'total_income': float(total_income),
        'total_expense': float(total_expense),
        'deductible_expense': float(deductible_expense),
        'income_count': len(incomes),
        'expense_count': len(expenses),
        'balance': float(total_income - total_expense)
    }
