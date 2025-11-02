"""
Модель банковских транзакций
Автоматически загружаемые из банков через API
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db import Base


class BankTransaction(Base):
    """
    Банковские транзакции

    Загружаются автоматически из банков (Точка, Альфа, Т-Банк)
    """
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)

    # ID транзакции в банке (уникальный)
    bank_transaction_id = Column(String(255), unique=True, index=True, nullable=False)

    # Банк
    # tochka - Точка Банк
    # alpha - Альфа-Банк
    # tinkoff - Т-Банк
    bank = Column(String(50), nullable=False, index=True)

    # Дата операции
    operation_date = Column(DateTime, nullable=False, index=True)

    # Дата валютирования
    value_date = Column(Date)

    # Сумма (положительная - приход, отрицательная - расход)
    amount = Column(Numeric(15, 2), nullable=False)

    # Валюта
    currency = Column(String(3), default="RUB")

    # Назначение платежа
    purpose = Column(Text, nullable=False)

    # Контрагент
    counterparty_name = Column(String(500))
    counterparty_inn = Column(String(12))
    counterparty_kpp = Column(String(9))
    counterparty_account = Column(String(20))
    counterparty_bank = Column(String(500))
    counterparty_bik = Column(String(9))

    # Номер документа
    document_number = Column(String(50))

    # Тип операции (INCOME/OUTCOME)
    operation_type = Column(String(50), nullable=False)

    # Статус в банке
    # executed - исполнено
    # pending - в обработке
    # rejected - отклонено
    bank_status = Column(String(50), default="executed")

    # Категория (определяется GPT-4)
    # revenue - выручка
    # expense - расход
    # salary - зарплата
    # tax - налог
    # transfer - перевод между счетами
    # loan - кредит
    # other - прочее
    category = Column(String(50), index=True)

    # Подкатегория (детализация)
    subcategory = Column(String(255))

    # Уверенность GPT в категоризации (0-1)
    category_confidence = Column(Numeric(3, 2))

    # Связь с созданной транзакцией в бухгалтерии
    accounting_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    accounting_transaction = relationship("Transaction", back_populates="bank_transaction")

    # Статус обработки
    # new - новая, не обработана
    # processed - обработана, создана транзакция
    # ignored - игнорируется (техническая операция)
    # manual - требует ручной проверки
    processing_status = Column(String(50), default="new", index=True)

    # Сырые данные от банка (JSON)
    raw_data = Column(JSON)

    # Примечания
    notes = Column(Text)

    # Системные поля
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<BankTransaction {self.bank}: {self.amount} ₽ - {self.counterparty_name}>"

    @property
    def is_income(self):
        """Это приход?"""
        return self.amount > 0

    @property
    def is_expense(self):
        """Это расход?"""
        return self.amount < 0

    @property
    def absolute_amount(self):
        """Абсолютная сумма"""
        return abs(self.amount)

    @property
    def needs_review(self):
        """Требует ручной проверки?"""
        return (
            self.processing_status == "manual"
            or (self.category_confidence and self.category_confidence < 0.7)
            or not self.category
        )
