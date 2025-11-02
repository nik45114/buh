"""
Модель расчета налогов
УСН с учетом регионов (Саха-Якутия 2%, обособки 6%)
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func
from ..db import Base


class TaxCalculation(Base):
    """
    Расчет налогов

    Хранит расчеты налогов по периодам
    УСН с учетом региональных ставок
    """
    __tablename__ = "tax_calculations"

    id = Column(Integer, primary_key=True, index=True)

    # Период расчета
    year = Column(Integer, nullable=False, index=True)
    quarter = Column(Integer, nullable=False, index=True)  # 1, 2, 3, 4

    # Налог
    # usn - УСН
    # ndfl - НДФЛ
    # insurance - Страховые взносы
    tax_type = Column(String(50), nullable=False, index=True)

    # Регион для УСН
    # sakha - Саха-Якутия (основная, 2%)
    # separate - Обособленные (Тамбов и др., 6%)
    region = Column(String(50), index=True)

    # Ставка налога
    tax_rate = Column(Numeric(5, 4), nullable=False)  # 0.02 или 0.06

    # База налогообложения
    tax_base = Column(Numeric(15, 2), default=0)

    # Доходы
    income_total = Column(Numeric(15, 2), default=0)

    # Расходы (для УСН доходы-расходы, для справки)
    expense_total = Column(Numeric(15, 2), default=0)

    # Сумма налога к уплате
    tax_amount = Column(Numeric(15, 2), default=0)

    # Авансовые платежи (уплачено ранее в этом году)
    prepayments = Column(Numeric(15, 2), default=0)

    # К доплате/возврату
    # Положительное - нужно доплатить
    # Отрицательное - переплата
    amount_due = Column(Numeric(15, 2), default=0)

    # Срок уплаты
    payment_deadline = Column(Date, nullable=False)

    # Дата уплаты (фактическая)
    payment_date = Column(Date)

    # Статус
    # calculated - рассчитан
    # paid - оплачен
    # overdue - просрочен
    # filed - сдана декларация
    status = Column(String(50), default="calculated", index=True)

    # Детализация расчета (JSON)
    # {
    #   "transactions_count": 150,
    #   "by_month": {
    #     "01": {"income": 50000, "expense": 10000},
    #     ...
    #   }
    # }
    calculation_details = Column(JSON)

    # Примечания
    notes = Column(Text)

    # Системные поля
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<TaxCalculation {self.tax_type} {self.year}Q{self.quarter}: {self.tax_amount} ₽>"

    @property
    def period_name(self):
        """Название периода"""
        return f"{self.year} Q{self.quarter}"

    @property
    def is_overdue(self):
        """Просрочен ли платеж"""
        if not self.payment_deadline:
            return False
        from datetime import date
        return date.today() > self.payment_deadline and self.status != "paid"

    @property
    def days_until_deadline(self):
        """Дней до срока уплаты"""
        if not self.payment_deadline:
            return None
        from datetime import date
        delta = self.payment_deadline - date.today()
        return delta.days


class TaxPayment(Base):
    """
    Уплата налогов

    Факт уплаты налога
    """
    __tablename__ = "tax_payments"

    id = Column(Integer, primary_key=True, index=True)

    # Связь с расчетом
    calculation_id = Column(Integer, ForeignKey("tax_calculations.id"), nullable=True)

    # Тип налога
    tax_type = Column(String(50), nullable=False, index=True)

    # Период
    year = Column(Integer, nullable=False)
    quarter = Column(Integer)
    month = Column(Integer)

    # Сумма
    amount = Column(Numeric(15, 2), nullable=False)

    # Дата уплаты
    payment_date = Column(Date, nullable=False, index=True)

    # Платежное поручение
    payment_order_number = Column(String(50))

    # КБК
    kbk = Column(String(20))

    # ОКТМО
    oktmo = Column(String(11))

    # Примечания
    notes = Column(Text)

    # Системные поля
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<TaxPayment {self.tax_type}: {self.amount} ₽ ({self.payment_date})>"
