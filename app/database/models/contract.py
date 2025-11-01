"""
Модель договора
"""
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Numeric, Text, ForeignKey, CheckConstraint, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..models import Base


class Contract(Base):
    """Договоры с сотрудниками"""
    __tablename__ = 'contracts'

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    contract_type = Column(String(20), nullable=False)
    contract_number = Column(String(50))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    position = Column(String(255))
    salary = Column(Numeric(10, 2))
    work_conditions = Column(Text)
    file_path = Column(String(500))
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "contract_type IN ('TD', 'GPH', 'OFFER')",
            name='check_contract_type'
        ),
        Index('idx_contracts_employee', 'employee_id'),
        Index('idx_contracts_type', 'contract_type'),
        Index('idx_contracts_number', 'contract_number'),
    )

    # Relationships
    employee = relationship('Employee', back_populates='contracts')

    @property
    def is_active(self):
        """Активный договор?"""
        from datetime import date
        today = date.today()
        if self.end_date is None:
            return self.start_date <= today
        return self.start_date <= today <= self.end_date
