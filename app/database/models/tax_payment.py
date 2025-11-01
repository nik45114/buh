"""
Модель налогового платежа
"""
from sqlalchemy import (
    Column, Integer, Date, DateTime, Numeric, String, CheckConstraint, Index
)
from sqlalchemy.sql import func
from ..models import Base


class TaxPayment(Base):
    """Налоги и взносы"""
    __tablename__ = 'tax_payments'

    id = Column(Integer, primary_key=True)
    tax_type = Column(String(50), nullable=False)
    period_quarter = Column(Integer)
    period_year = Column(Integer, nullable=False)
    base_amount = Column(Numeric(10, 2))
    tax_amount = Column(Numeric(10, 2), nullable=False)
    payment_deadline = Column(Date, nullable=False, index=True)
    payment_date = Column(Date)
    status = Column(String(20), default='CALCULATED', nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "tax_type IN ('USN', 'NDFL', 'PENSION', 'MEDICAL', 'SOCIAL', 'INJURY')",
            name='check_tax_type'
        ),
        CheckConstraint(
            "status IN ('CALCULATED', 'PAID', 'OVERDUE')",
            name='check_tax_payment_status'
        ),
        CheckConstraint("period_quarter BETWEEN 1 AND 4", name='check_tax_quarter'),
        CheckConstraint("period_year >= 2020", name='check_tax_year'),
        Index('idx_tax_payments_type', 'tax_type'),
        Index('idx_tax_payments_status', 'status'),
        Index('idx_tax_payments_period', 'period_year', 'period_quarter'),
        Index('idx_tax_payments_deadline', 'payment_deadline'),
    )

    @property
    def is_overdue(self):
        """Просрочен?"""
        from datetime import date
        return self.status != 'PAID' and self.payment_deadline < date.today()

    @property
    def period_name(self):
        """Название периода"""
        if self.period_quarter:
            return f"{self.period_quarter} квартал {self.period_year}"
        return f"{self.period_year} год"
