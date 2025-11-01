"""
Модель смены
"""
from sqlalchemy import (
    Column, Integer, Date, Time, DateTime, Numeric, Text, ForeignKey, Boolean, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..models import Base


class Shift(Base):
    """Смены сотрудников (импортируются из Bot_Claude)"""
    __tablename__ = 'shifts'

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id', ondelete='SET NULL'))
    shift_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time)
    end_time = Column(Time)
    hours_worked = Column(Numeric(5, 2))
    revenue = Column(Numeric(10, 2))
    expenses = Column(Numeric(10, 2))
    notes = Column(Text)
    imported_from_bot = Column(Boolean, default=False)
    bot_shift_id = Column(Integer)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_shifts_employee', 'employee_id'),
        Index('idx_shifts_date', 'shift_date'),
        Index('idx_shifts_imported', 'imported_from_bot'),
        Index('idx_shifts_bot_id', 'bot_shift_id', unique=True),
    )

    # Relationships
    employee = relationship('Employee', back_populates='shifts')

    @property
    def salary_amount(self):
        """Расчет зарплаты за смену"""
        if self.hours_worked and self.employee and self.employee.hourly_rate:
            return self.hours_worked * self.employee.hourly_rate
        return None
