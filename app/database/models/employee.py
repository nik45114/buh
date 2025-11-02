"""
Модель сотрудника
"""
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Numeric, Text, CheckConstraint, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..models import Base


class Employee(Base):
    """Сотрудники"""
    __tablename__ = 'employees'

    id = Column(Integer, primary_key=True)
    full_name = Column(String(255), nullable=False)
    inn = Column(String(12), unique=True)
    snils = Column(String(14))
    passport_series = Column(String(4))
    passport_number = Column(String(6))
    passport_issued_by = Column(Text)
    passport_issue_date = Column(Date)
    birth_date = Column(Date)
    birth_place = Column(Text)
    registration_address = Column(Text)
    phone = Column(String(20))
    email = Column(String(255))
    employment_type = Column(String(20))
    hire_date = Column(Date)
    fire_date = Column(Date)
    hourly_rate = Column(Numeric(10, 2))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "employment_type IN ('TD', 'GPH', 'OFFER', 'SELF_EMPLOYED')",
            name='check_employment_type'
        ),
        Index('idx_employees_inn', 'inn'),
        Index('idx_employees_employment_type', 'employment_type'),
    )

    # Relationships
    contracts = relationship('Contract', back_populates='employee', cascade='all, delete-orphan')
    shifts = relationship('Shift', back_populates='employee')
    payroll = relationship('Payroll', back_populates='employee')
    accountable_records = relationship('Accountable', back_populates='employee')

    @property
    def is_active(self):
        """Активный сотрудник?"""
        return self.fire_date is None

    @property
    def full_passport(self):
        """Полные паспортные данные"""
        if self.passport_series and self.passport_number:
            return f"{self.passport_series} {self.passport_number}"
        return None
