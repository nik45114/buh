"""
Модель напоминания
"""
from sqlalchemy import (
    Column, Integer, Date, DateTime, String, Text, CheckConstraint, Index
)
from sqlalchemy.sql import func
from ..models import Base


class Reminder(Base):
    """Напоминания о важных событиях"""
    __tablename__ = 'reminders'

    id = Column(Integer, primary_key=True)
    reminder_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    due_date = Column(Date, nullable=False, index=True)
    priority = Column(String(20), default='MEDIUM', nullable=False)
    status = Column(String(20), default='PENDING', nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name='check_reminder_priority'
        ),
        CheckConstraint(
            "status IN ('PENDING', 'SENT', 'COMPLETED')",
            name='check_reminder_status'
        ),
        Index('idx_reminders_type', 'reminder_type'),
        Index('idx_reminders_status', 'status'),
        Index('idx_reminders_priority', 'priority'),
        Index('idx_reminders_due_date', 'due_date'),
    )

    @property
    def is_overdue(self):
        """Просрочено?"""
        from datetime import date
        return self.status == 'PENDING' and self.due_date < date.today()

    @property
    def priority_emoji(self):
        """Emoji для приоритета"""
        emojis = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🟠',
            'CRITICAL': '🔴'
        }
        return emojis.get(self.priority, '⚪')
