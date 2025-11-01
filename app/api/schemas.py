"""
Pydantic схемы для API
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date
from decimal import Decimal


class ShiftReportSchema(BaseModel):
    """Схема отчета о смене"""
    date: date
    shift: str = Field(..., pattern="^(morning|evening)$")
    cash_fact: Optional[Decimal] = None
    cash_plan: Optional[Decimal] = None
    cashless_fact: Optional[Decimal] = None
    qr_payments: Optional[Decimal] = None
    safe: Optional[Decimal] = None
    expenses: Optional[List[Dict]] = None
    workers: Optional[List[str]] = None
    equipment_issues: Optional[List[str]] = None
    z_report_data: Optional[Dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-01-15",
                "shift": "evening",
                "cash_fact": 15000.00,
                "cash_plan": 14500.00,
                "cashless_fact": 8000.00,
                "qr_payments": 3500.00,
                "safe": 5000.00,
                "expenses": [
                    {"amount": 500, "description": "Вода для кулера"},
                    {"amount": 1200, "description": "Канцтовары"}
                ],
                "workers": ["Иван", "Мария"],
                "equipment_issues": ["ПК #5 - не работает мышь"]
            }
        }


class TransactionSchema(BaseModel):
    """Схема транзакции"""
    date: date
    type: str = Field(..., pattern="^(income|expense)$")
    amount: Decimal = Field(..., gt=0)
    category_id: Optional[int] = None
    counterparty: Optional[str] = None
    counterparty_inn: Optional[str] = None
    description: Optional[str] = None
    payment_method: Optional[str] = Field(None, pattern="^(cash|cashless|card|qr|mixed)$")
    document_number: Optional[str] = None
    document_date: Optional[date] = None
    is_confirmed: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-01-15",
                "type": "expense",
                "amount": 5000.00,
                "category_id": 1,
                "counterparty": "ООО Поставщик",
                "counterparty_inn": "1234567890",
                "description": "Закупка оборудования",
                "payment_method": "cashless",
                "is_confirmed": False
            }
        }


class ResponseSchema(BaseModel):
    """Схема ответа API"""
    status: str
    message: Optional[str] = None
    data: Optional[Dict] = None


class ErrorSchema(BaseModel):
    """Схема ошибки"""
    status: str = "error"
    detail: str
