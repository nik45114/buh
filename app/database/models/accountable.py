"""
Модель подотчетных сумм
Учет выданных наличных под отчет
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db import Base


class Accountable(Base):
    """
    Подотчетные суммы

    Когда сотрудник берет деньги из кассы - создается запись.
    Когда отчитывается чеками - запись закрывается.
    Если не отчитался - сумма облагается НДФЛ.
    """
    __tablename__ = "accountable"

    id = Column(Integer, primary_key=True, index=True)

    # Сотрудник
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    employee = relationship("Employee", back_populates="accountable_records")

    # Дата выдачи
    issued_date = Column(Date, nullable=False, index=True)

    # Сумма выданная
    amount_issued = Column(Numeric(10, 2), nullable=False)

    # Сумма отчитанная чеками
    amount_reported = Column(Numeric(10, 2), default=0)

    # Статус
    # pending - выдано, ждем отчет
    # reported - отчитался полностью
    # partial - отчитался частично
    # overdue - просрочен срок отчета (3 дня по ТК РФ)
    # taxed - не отчитался, начислен НДФЛ
    status = Column(String(50), default="pending", index=True)

    # Назначение (на что выдано)
    purpose = Column(Text)

    # Срок отчета (по ТК РФ - 3 дня после возвращения из командировки или траты)
    report_deadline = Column(Date, nullable=False)

    # Дата отчета (когда отчитался)
    reported_date = Column(Date, nullable=True)

    # Примечания
    notes = Column(Text)

    # Системные поля
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связь с чеками
    receipts = relationship("Receipt", back_populates="accountable", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Accountable {self.employee.name if self.employee else 'N/A'}: {self.amount_issued} ₽ ({self.status})>"

    @property
    def amount_remaining(self):
        """Сумма, которую еще нужно отчитать"""
        return self.amount_issued - self.amount_reported

    @property
    def is_overdue(self):
        """Просрочен ли срок отчета"""
        from datetime import date
        return date.today() > self.report_deadline and self.status == "pending"

    @property
    def should_be_taxed(self):
        """Нужно ли начислить НДФЛ (не отчитался в срок)"""
        return self.is_overdue and self.amount_remaining > 0
