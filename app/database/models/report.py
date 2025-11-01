"""
Модель отчета
"""
from sqlalchemy import (
    Column, Integer, Date, DateTime, String, CheckConstraint, Index
)
from sqlalchemy.sql import func
from ..models import Base


class Report(Base):
    """Отчеты в налоговую и фонды"""
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True)
    report_type = Column(String(50), nullable=False)
    period_quarter = Column(Integer)
    period_year = Column(Integer, nullable=False)
    file_path = Column(String(500))
    xml_path = Column(String(500))
    status = Column(String(20), default='DRAFT', nullable=False)
    sent_date = Column(Date)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "report_type IN ('USN_DECLARATION', 'RSV', 'SZV_M', 'EFS_1', 'KUDIR')",
            name='check_report_type'
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'READY', 'SENT', 'ACCEPTED')",
            name='check_report_status'
        ),
        CheckConstraint("period_quarter BETWEEN 1 AND 4", name='check_report_quarter'),
        CheckConstraint("period_year >= 2020", name='check_report_year'),
        Index('idx_reports_type', 'report_type'),
        Index('idx_reports_status', 'status'),
        Index('idx_reports_period', 'period_year', 'period_quarter'),
    )

    @property
    def period_name(self):
        """Название периода"""
        if self.period_quarter:
            return f"{self.period_quarter} квартал {self.period_year}"
        return f"{self.period_year} год"

    @property
    def type_name(self):
        """Человекочитаемое название отчета"""
        names = {
            'USN_DECLARATION': 'Декларация УСН',
            'RSV': 'Расчет страховых взносов (РСВ)',
            'SZV_M': 'СЗВ-М',
            'EFS_1': 'ЕФС-1',
            'KUDIR': 'Книга учета доходов и расходов'
        }
        return names.get(self.report_type, self.report_type)
