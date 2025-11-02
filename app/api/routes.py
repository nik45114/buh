"""
API маршруты
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from app.api.schemas import (
    ShiftReportSchema, TransactionSchema, ResponseSchema,
    ReceiptSchema, CashWithdrawalSchema, AccountableReportSchema
)
from app.database.db import async_session_maker
from app.database import crud
from app.config import settings
from datetime import datetime, date as date_type, timedelta
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Schema для проверки смены
class ShiftCheckSchema(BaseModel):
    date: date_type
    cash: float
    cashless: float
    qr: float = 0.0
    kkt_number: Optional[str] = None


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


@router.post("/check-shift")
async def check_shift_with_ofd(
    check_data: ShiftCheckSchema,
    api_key: str = Depends(verify_api_key)
):
    """
    Проверить смену с данными онлайн-кассы СБИС ОФД

    - **date**: Дата смены
    - **cash**: Фактические наличные
    - **cashless**: Фактический безнал
    - **qr**: QR платежи
    - **kkt_number**: Номер ККТ (опционально)

    Возвращает результат сверки с кассой
    """
    try:
        from app.services.sbis_ofd import validate_shift_with_ofd, get_shift_validation_report

        # Проверить с СБИС ОФД
        validation = await validate_shift_with_ofd(
            shift_date=check_data.date,
            fact_cash=check_data.cash,
            fact_cashless=check_data.cashless,
            fact_qr=check_data.qr,
            kkt_number=check_data.kkt_number
        )

        # Получить полный отчет
        report = await get_shift_validation_report(
            shift_date=check_data.date,
            fact_cash=check_data.cash,
            fact_cashless=check_data.cashless,
            fact_qr=check_data.qr,
            kkt_number=check_data.kkt_number
        )

        return {
            "status": validation.get("status", "error"),
            "is_closed": validation.get("is_closed", False),
            "message": validation.get("message", ""),
            "discrepancies": validation.get("discrepancies"),
            "report": report
        }

    except Exception as e:
        logger.error(f"Error checking shift with OFD: {e}")
        return {
            "status": "error",
            "message": f"Ошибка проверки с СБИС ОФД: {str(e)}"
        }


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


@router.post("/receipt")
async def receive_receipt(
    receipt_data: ReceiptSchema,
    api_key: str = Depends(verify_api_key)
):
    """
    Прием чека от Bot_Claude (по QR-коду ФНС)

    - **qr_data**: Данные QR-кода с чека
    - **accountable_id**: ID подотчетной суммы (если отчет)
    - **category**: Категория расхода
    - **notes**: Примечания
    """
    try:
        from app.services.fns_receipt import fns_receipt_service
        from app.database.models import Receipt, Accountable, Transaction

        # Декодируем QR и получаем данные от ФНС
        receipt_info = await fns_receipt_service.verify_and_save_receipt(receipt_data.qr_data)

        if not receipt_info:
            raise HTTPException(status_code=400, detail="Invalid QR code or FNS API unavailable")

        async with async_session_maker() as session:
            # Создаем запись чека
            new_receipt = Receipt(
                fiscal_sign=receipt_info["fiscal_sign"],
                fiscal_document=receipt_info["fiscal_document"],
                fiscal_storage=receipt_info["fiscal_storage"],
                purchase_date=receipt_info["purchase_date"],
                total_amount=receipt_info["total_amount"],
                vat_amount=receipt_info.get("vat_amount", 0),
                seller_name=receipt_info.get("seller_name"),
                seller_inn=receipt_info.get("seller_inn"),
                seller_address=receipt_info.get("seller_address"),
                cashier=receipt_info.get("cashier"),
                shift_number=receipt_info.get("shift_number"),
                operation_type=receipt_info["operation_type"],
                items=receipt_info.get("items"),
                payment_type=receipt_info.get("payment_type", "cash"),
                taxation_type=receipt_info.get("taxation_type"),
                qr_raw=receipt_info["qr_raw"],
                fns_url=receipt_info.get("fns_url"),
                category=receipt_data.category,
                notes=receipt_data.notes,
                accountable_id=receipt_data.accountable_id,
                status="verified"
            )

            session.add(new_receipt)
            await session.flush()

            # Создаем транзакцию расхода
            new_transaction = Transaction(
                date=receipt_info["purchase_date"].date(),
                type="expense",
                amount=receipt_info["total_amount"],
                description=f"Чек от {receipt_info.get('seller_name', 'N/A')}",
                counterparty=receipt_info.get("seller_name"),
                counterparty_inn=receipt_info.get("seller_inn"),
                payment_method=receipt_info.get("payment_type", "cash"),
                source="receipt_qr",
                is_confirmed=False  # Требует подтверждения
            )

            session.add(new_transaction)
            await session.flush()

            # Связываем чек и транзакцию
            new_receipt.transaction_id = new_transaction.id

            # Если это отчет по подотчету - обновляем подотчет
            if receipt_data.accountable_id:
                result = await session.execute(
                    select(Accountable).where(Accountable.id == receipt_data.accountable_id)
                )
                accountable = result.scalar_one_or_none()

                if accountable:
                    accountable.amount_reported += receipt_info["total_amount"]

                    # Проверяем статус
                    if accountable.amount_reported >= accountable.amount_issued:
                        accountable.status = "reported"
                        accountable.reported_date = date_type.today()
                    else:
                        accountable.status = "partial"

            await session.commit()

            logger.info(f"Receipt created: {new_receipt.fiscal_sign}, transaction: {new_transaction.id}")

            return {
                "status": "success",
                "message": "Receipt processed successfully",
                "data": {
                    "receipt_id": new_receipt.id,
                    "transaction_id": new_transaction.id,
                    "total_amount": float(receipt_info["total_amount"]),
                    "seller": receipt_info.get("seller_name"),
                    "fns_url": receipt_info.get("fns_url")
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing receipt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cash-withdrawal")
async def create_cash_withdrawal(
    withdrawal_data: CashWithdrawalSchema,
    api_key: str = Depends(verify_api_key)
):
    """
    Выдача наличных под отчет из Bot_Claude

    - **employee_name**: ФИО сотрудника
    - **amount**: Сумма выдачи
    - **purpose**: Назначение
    - **report_deadline_days**: Срок отчета (дней)
    """
    try:
        from app.database.models import Employee, Accountable, Transaction

        async with async_session_maker() as session:
            # Ищем сотрудника по имени
            result = await session.execute(
                select(Employee).where(Employee.full_name.ilike(f"%{withdrawal_data.employee_name}%"))
            )
            employee = result.scalar_one_or_none()

            if not employee:
                raise HTTPException(
                    status_code=404,
                    detail=f"Employee not found: {withdrawal_data.employee_name}"
                )

            # Создаем запись подотчета
            report_deadline = date_type.today() + timedelta(days=withdrawal_data.report_deadline_days)

            new_accountable = Accountable(
                employee_id=employee.id,
                issued_date=date_type.today(),
                amount_issued=withdrawal_data.amount,
                amount_reported=0,
                status="pending",
                purpose=withdrawal_data.purpose,
                report_deadline=report_deadline,
                notes=withdrawal_data.notes
            )

            session.add(new_accountable)
            await session.flush()

            # Создаем транзакцию расхода (выдача из кассы)
            new_transaction = Transaction(
                date=date_type.today(),
                type="expense",
                amount=withdrawal_data.amount,
                description=f"Выдано под отчет: {employee.full_name} - {withdrawal_data.purpose}",
                payment_method="cash",
                source="accountable",
                is_confirmed=True  # Автоматически подтверждаем выдачу
            )

            session.add(new_transaction)
            await session.commit()

            logger.info(
                f"Cash withdrawal created: {employee.full_name}, "
                f"{withdrawal_data.amount} ₽, accountable_id: {new_accountable.id}"
            )

            return {
                "status": "success",
                "message": "Cash withdrawal registered",
                "data": {
                    "accountable_id": new_accountable.id,
                    "employee": employee.full_name,
                    "amount": float(withdrawal_data.amount),
                    "report_deadline": report_deadline.isoformat(),
                    "transaction_id": new_transaction.id
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating cash withdrawal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accountable-report")
async def submit_accountable_report(
    report_data: AccountableReportSchema,
    api_key: str = Depends(verify_api_key)
):
    """
    Отчет по подотчетной сумме (несколько чеков)

    - **accountable_id**: ID подотчетной суммы
    - **receipts**: Массив QR-кодов чеков
    """
    try:
        from app.services.fns_receipt import fns_receipt_service
        from app.database.models import Accountable

        async with async_session_maker() as session:
            # Получаем подотчет
            result = await session.execute(
                select(Accountable).where(Accountable.id == report_data.accountable_id)
            )
            accountable = result.scalar_one_or_none()

            if not accountable:
                raise HTTPException(status_code=404, detail="Accountable record not found")

            receipts_created = []
            total_reported = Decimal("0")

            # Обрабатываем каждый чек
            for qr_data in report_data.receipts:
                # Используем endpoint /receipt
                receipt_schema = ReceiptSchema(
                    qr_data=qr_data,
                    accountable_id=report_data.accountable_id,
                    notes=report_data.notes
                )

                # Вызываем обработчик чека
                result = await receive_receipt(receipt_schema, api_key=settings.API_KEY)
                receipts_created.append(result["data"])
                total_reported += Decimal(str(result["data"]["total_amount"]))

            # Обновляем статус подотчета (это уже сделано в receive_receipt, но перепроверяем)
            await session.refresh(accountable)

            return {
                "status": "success",
                "message": f"Report submitted: {len(receipts_created)} receipts processed",
                "data": {
                    "accountable_id": accountable.id,
                    "amount_issued": float(accountable.amount_issued),
                    "amount_reported": float(accountable.amount_reported),
                    "amount_remaining": float(accountable.amount_remaining),
                    "status": accountable.status,
                    "receipts": receipts_created
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting accountable report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
