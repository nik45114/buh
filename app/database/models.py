"""
SQLAlchemy модели базы данных
"""
from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, Boolean,
    Text, ForeignKey, CheckConstraint, Index, ARRAY, BigInteger
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """Пользователи бота"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100))
    full_name = Column(String(200))
    role = Column(String(20), default='user', nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'accountant', 'user')", name='check_user_role'),
        Index('idx_users_role', 'role'),
    )

    # Relationships
    created_transactions = relationship('Transaction', foreign_keys='Transaction.created_by', back_populates='creator')
    confirmed_transactions = relationship('Transaction', foreign_keys='Transaction.confirmed_by', back_populates='confirmer')


class Category(Base):
    """Категории доходов и расходов"""
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(String(10), nullable=False)
    tax_deductible = Column(Boolean, default=True)
    parent_id = Column(Integer, ForeignKey('categories.id'))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name='check_category_type'),
        Index('idx_categories_type', 'type'),
        Index('idx_categories_active', 'is_active'),
    )

    # Relationships
    transactions = relationship('Transaction', back_populates='category')
    parent = relationship('Category', remote_side=[id])


class Transaction(Base):
    """Основная таблица транзакций"""
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    type = Column(String(10), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    counterparty = Column(String(255))
    counterparty_inn = Column(String(12))
    description = Column(Text)
    payment_method = Column(String(20))
    source = Column(String(50), default='manual')
    document_number = Column(String(100))
    document_date = Column(Date)
    is_confirmed = Column(Boolean, default=False)
    is_kudir_included = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    created_by = Column(Integer, ForeignKey('users.id'))
    confirmed_at = Column(DateTime)
    confirmed_by = Column(Integer, ForeignKey('users.id'))
    notes = Column(Text)

    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name='check_transaction_type'),
        CheckConstraint("amount > 0", name='check_positive_amount'),
        CheckConstraint(
            "payment_method IN ('cash', 'cashless', 'card', 'qr', 'mixed')",
            name='check_payment_method'
        ),
        Index('idx_transactions_type', 'type'),
        Index('idx_transactions_confirmed', 'is_confirmed'),
        Index('idx_transactions_category', 'category_id'),
        Index('idx_transactions_source', 'source'),
    )

    # Relationships
    category = relationship('Category', back_populates='transactions')
    creator = relationship('User', foreign_keys=[created_by], back_populates='created_transactions')
    confirmer = relationship('User', foreign_keys=[confirmed_by], back_populates='confirmed_transactions')
    documents = relationship('Document', back_populates='transaction', cascade='all, delete-orphan')


class Document(Base):
    """Документы (чеки, акты, счета)"""
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id', ondelete='CASCADE'))
    file_path = Column(String(500))
    file_type = Column(String(50))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    telegram_file_id = Column(String(500))
    ocr_text = Column(Text)
    ocr_data = Column(JSONB)
    uploaded_at = Column(DateTime, default=func.now())
    uploaded_by = Column(Integer, ForeignKey('users.id'))

    __table_args__ = (
        Index('idx_documents_transaction', 'transaction_id'),
        Index('idx_documents_type', 'file_type'),
    )

    # Relationships
    transaction = relationship('Transaction', back_populates='documents')
    uploader = relationship('User')


class CashBalance(Base):
    """Баланс кассы (ежедневная сверка)"""
    __tablename__ = 'cash_balance'

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    opening_balance = Column(Numeric(12, 2), default=0)
    closing_balance = Column(Numeric(12, 2), nullable=False)
    calculated_balance = Column(Numeric(12, 2))
    is_reconciled = Column(Boolean, default=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    reconciled_by = Column(Integer, ForeignKey('users.id'))
    reconciled_at = Column(DateTime)

    __table_args__ = (
        Index('idx_cash_balance_reconciled', 'is_reconciled'),
    )

    # Relationships
    reconciler = relationship('User')

    @property
    def difference(self):
        """Разница между фактом и расчетом"""
        if self.calculated_balance is not None:
            return self.closing_balance - self.calculated_balance
        return None


class ShiftReport(Base):
    """Отчеты о сменах (из Bot_Claude)"""
    __tablename__ = 'shift_reports'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    shift = Column(String(20))
    cash_fact = Column(Numeric(10, 2))
    cash_plan = Column(Numeric(10, 2))
    cashless_fact = Column(Numeric(10, 2))
    qr_payments = Column(Numeric(10, 2))
    safe = Column(Numeric(10, 2))
    expenses = Column(JSONB)
    workers = Column(ARRAY(Text))
    equipment_issues = Column(ARRAY(Text))
    z_report_data = Column(JSONB)
    received_at = Column(DateTime, default=func.now())
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)

    __table_args__ = (
        CheckConstraint("shift IN ('morning', 'evening')", name='check_shift_type'),
        Index('idx_shift_reports_processed', 'processed'),
        Index('idx_shift_reports_unique', 'date', 'shift', unique=True),
    )

    @property
    def cash_diff(self):
        """Разница между фактом и планом по наличке"""
        if self.cash_fact is not None and self.cash_plan is not None:
            return self.cash_fact - self.cash_plan
        return None

    @property
    def total_revenue(self):
        """Общая выручка"""
        total = 0
        if self.cash_fact:
            total += self.cash_fact
        if self.cashless_fact:
            total += self.cashless_fact
        if self.qr_payments:
            total += self.qr_payments
        return total


class Setting(Base):
    """Настройки системы"""
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    value_type = Column(String(20))
    description = Column(Text)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey('users.id'))

    __table_args__ = (
        CheckConstraint(
            "value_type IN ('string', 'number', 'boolean', 'json')",
            name='check_value_type'
        ),
    )

    # Relationships
    updater = relationship('User')


class AuditLog(Base):
    """Логи операций (аудит)"""
    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    action = Column(String(50), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    old_data = Column(JSONB)
    new_data = Column(JSONB)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=func.now(), index=True)

    __table_args__ = (
        Index('idx_audit_log_user', 'user_id'),
        Index('idx_audit_log_action', 'action'),
    )

    # Relationships
    user = relationship('User')
