"""
API маршруты
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from app.api.schemas import ShiftReportSchema, TransactionSchema, ResponseSchema
from app.database.db import async_session_maker
from app.database import crud
from app.config import settings
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Проверка API ключа"""
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key


@router.post("/shift-report", response_model=ResponseSchema)
async def receive_shift_report(
    report: ShiftReportSchema,
    api_key: str = Depends(verify_api_key)
):
    """
    Прием отчета о смене от Bot_Claude

    - **date**: Дата смены
    - **shift**: Смена (morning/evening)
    - **cash_fact**: Фактическая наличка
    - **cashless_fact**: Безналичные платежи
    - **qr_payments**: Платежи по QR
    - **expenses**: Массив расходов со смены
    """
    try:
        async with async_session_maker() as session:
            # Сохранение отчета
            db_report = await crud.create_shift_report(session, report.dict())

            # Автоматическое создание транзакций
            transactions_created = []

            # 1. Доход = cash + cashless + qr
            income_amount = Decimal('0')
            if report.cash_fact:
                income_amount += report.cash_fact
            if report.cashless_fact:
                income_amount += report.cashless_fact
            if report.qr_payments:
                income_amount += report.qr_payments

            if income_amount > 0:
                income_transaction = await crud.create_transaction(session, {
                    'date': report.date,
                    'type': 'income',
                    'amount': income_amount,
                    'description': f'Выручка смена {report.shift} {report.date}',
                    'payment_method': 'mixed',
                    'source': 'shift_report',
                    'is_confirmed': True  # Автоматически подтверждаем доходы из смен
                })
                transactions_created.append(income_transaction.id)

            # 2. Расходы из expenses
            if report.expenses:
                for expense in report.expenses:
                    expense_transaction = await crud.create_transaction(session, {
                        'date': report.date,
                        'type': 'expense',
                        'amount': Decimal(str(expense.get('amount', 0))),
                        'description': expense.get('description', 'Расход со смены'),
                        'source': 'shift_report',
                        'is_confirmed': False  # Требует подтверждения
                    })
                    transactions_created.append(expense_transaction.id)

            logger.info(
                f"Shift report received: {report.date} {report.shift}, "
                f"created {len(transactions_created)} transactions"
            )

            return ResponseSchema(
                status="success",
                message="Shift report processed successfully",
                data={
                    "report_id": db_report.id,
                    "transactions_created": transactions_created,
                    "total_revenue": float(income_amount)
                }
            )

    except Exception as e:
        logger.error(f"Error processing shift report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transaction", response_model=ResponseSchema)
async def create_transaction_api(
    transaction: TransactionSchema,
    api_key: str = Depends(verify_api_key)
):
    """
    Создание транзакции через API

    - **type**: Тип (income/expense)
    - **amount**: Сумма
    - **date**: Дата операции
    - **category_id**: ID категории
    - **counterparty**: Контрагент
    - **description**: Описание
    """
    try:
        async with async_session_maker() as session:
            db_transaction = await crud.create_transaction(session, transaction.dict())

            return ResponseSchema(
                status="success",
                message="Transaction created successfully",
                data={
                    "transaction_id": db_transaction.id,
                    "type": db_transaction.type,
                    "amount": float(db_transaction.amount)
                }
            )

    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=ResponseSchema)
async def get_stats(
    api_key: str = Depends(verify_api_key),
    year: int = None,
    month: int = None
):
    """
    Получить статистику

    - **year**: Год (по умолчанию текущий)
    - **month**: Месяц (опционально)
    """
    try:
        from datetime import date
        import calendar

        if not year:
            year = datetime.now().year

        if month:
            start_date = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = date(year, month, last_day)
        else:
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)

        async with async_session_maker() as session:
            stats = await crud.get_period_statistics(session, start_date, end_date)

        return ResponseSchema(
            status="success",
            data=stats
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions/{transaction_id}", response_model=ResponseSchema)
async def get_transaction(
    transaction_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Получить транзакцию по ID"""
    try:
        async with async_session_maker() as session:
            transaction = await crud.get_transaction_by_id(session, transaction_id)

            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found")

            return ResponseSchema(
                status="success",
                data={
                    "id": transaction.id,
                    "date": transaction.date.isoformat(),
                    "type": transaction.type,
                    "amount": float(transaction.amount),
                    "category": transaction.category.name if transaction.category else None,
                    "description": transaction.description,
                    "is_confirmed": transaction.is_confirmed
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transactions/{transaction_id}/confirm", response_model=ResponseSchema)
async def confirm_transaction_api(
    transaction_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Подтвердить транзакцию"""
    try:
        async with async_session_maker() as session:
            # Используем ID владельца как системного пользователя для API
            transaction = await crud.confirm_transaction(
                session,
                transaction_id,
                user_id=1  # Системный пользователь
            )

            return ResponseSchema(
                status="success",
                message="Transaction confirmed",
                data={
                    "transaction_id": transaction.id,
                    "confirmed_at": transaction.confirmed_at.isoformat() if transaction.confirmed_at else None
                }
            )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error confirming transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Проверка здоровья API"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "Accounting Bot API"
    }
