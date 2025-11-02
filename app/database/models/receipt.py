"""
Модель чеков (расходных документов)
Хранение чеков от ФНС по QR-коду
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db import Base


class Receipt(Base):
    """
    Чеки (расходные документы)

    Хранит данные чеков полученных через QR-код ФНС
    """
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)

    # Связь с подотчетной суммой (если это отчет по подотчету)
    accountable_id = Column(Integer, ForeignKey("accountable.id"), nullable=True)
    accountable = relationship("Accountable", back_populates="receipts")

    # Связь с транзакцией
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    transaction = relationship("Transaction", back_populates="receipt")

    # Данные чека от ФНС
    # ФП (фискальный признак)
    fiscal_sign = Column(String(50), unique=True, index=True)

    # ФД (фискальный документ)
    fiscal_document = Column(String(50))

    # ФН (фискальный накопитель)
    fiscal_storage = Column(String(50))

    # Дата и время покупки
    purchase_date = Column(DateTime, nullable=False, index=True)

    # Сумма чека
    total_amount = Column(Numeric(10, 2), nullable=False)

    # НДС
    vat_amount = Column(Numeric(10, 2), default=0)

    # Продавец
    seller_name = Column(String(500))
    seller_inn = Column(String(12))

    # Адрес магазина
    seller_address = Column(Text)

    # Кассир
    cashier = Column(String(255))

    # Номер смены
    shift_number = Column(Integer)

    # Тип операции (приход/расход)
    operation_type = Column(String(50), default="income")

    # Товары (JSON массив)
    # [{"name": "Вода 5л", "quantity": 10, "price": 50, "sum": 500}, ...]
    items = Column(JSON)

    # Форма оплаты
    # cash - наличные
    # card - безналичные
    payment_type = Column(String(50), default="cash")

    # Тип налогообложения
    taxation_type = Column(String(50))

    # QR-код (сырые данные)
    qr_raw = Column(Text)

    # URL чека на сайте ФНС
    fns_url = Column(String(500))

    # Файл чека (если есть изображение)
    file_path = Column(String(500))

    # Статус проверки
    # pending - загружен, не проверен
    # verified - проверен в ФНС
    # approved - утвержден
    # rejected - отклонен
    status = Column(String(50), default="pending", index=True)

    # Примечания
    notes = Column(Text)

    # Категория расхода (определяется GPT-4 или вручную)
    category = Column(String(255))

    # Системные поля
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Receipt {self.fiscal_sign}: {self.total_amount} ₽ от {self.seller_name}>"

    @property
    def purchase_date_str(self):
        """Дата покупки в формате строки"""
        return self.purchase_date.strftime("%d.%m.%Y %H:%M") if self.purchase_date else ""

    @property
    def items_count(self):
        """Количество позиций в чеке"""
        return len(self.items) if self.items else 0
