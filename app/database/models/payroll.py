"""
Модель начисления зарплаты
"""
from sqlalchemy import (
    Column, Integer, Date, DateTime, Numeric, ForeignKey, String, CheckConstraint, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..models import Base


class Payroll(Base):
    """Начисления зарплаты"""
    __tablename__ = 'payroll'

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    total_hours = Column(Numeric(10, 2))
    gross_salary = Column(Numeric(10, 2))
    ndfl = Column(Numeric(10, 2))
    contributions = Column(Numeric(10, 2))
    net_salary = Column(Numeric(10, 2))
    payment_date = Column(Date)
    status = Column(String(20), default='DRAFT', nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'APPROVED', 'PAID')",
            name='check_payroll_status'
        ),
        CheckConstraint("period_month BETWEEN 1 AND 12", name='check_payroll_month'),
        CheckConstraint("period_year >= 2020", name='check_payroll_year'),
        Index('idx_payroll_employee', 'employee_id'),
        Index('idx_payroll_period', 'period_year', 'period_month'),
        Index('idx_payroll_status', 'status'),
        Index('idx_payroll_unique', 'employee_id', 'period_year', 'period_month', unique=True),
    )

    # Relationships
    employee = relationship('Employee', back_populates='payroll')

    @property
    def period_name(self):
        """Название периода"""
        months = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]
        return f"{months[self.period_month - 1]} {self.period_year}"
