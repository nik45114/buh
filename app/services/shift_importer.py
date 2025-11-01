"""
Импорт смен из Bot_Claude
"""
import logging
from datetime import date, datetime
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database.models import Employee, Shift, ShiftReport, Transaction, Category
from .bot_claude_sync import BotClaudeSync

logger = logging.getLogger(__name__)


class ShiftImporter:
    """Импорт смен из Bot_Claude в БД бухгалтерии"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.sync = BotClaudeSync()

    async def import_shifts(self, start_date: date, end_date: date) -> Dict[str, int]:
        """
        Импортировать смены за период

        Returns:
            Dict с количеством импортированных/обновленных записей
        """
        stats = {
            'shifts_imported': 0,
            'shifts_skipped': 0,
            'employees_created': 0,
            'transactions_created': 0
        }

        if not self.sync.is_available():
            logger.warning("Bot_Claude database not available, skipping import")
            return stats

        # Получить смены из Bot_Claude
        shifts_data = self.sync.fetch_shifts(start_date, end_date)

        for shift_data in shifts_data:
            # Проверить, не импортирована ли уже эта смена
            bot_shift_id = shift_data.get('bot_shift_id')
            existing = await self.session.execute(
                select(Shift).where(Shift.bot_shift_id == bot_shift_id)
            )
            if existing.scalar_one_or_none():
                stats['shifts_skipped'] += 1
                continue

            # Найти или создать сотрудника
            employee = await self._get_or_create_employee(shift_data['employee_name'])
            if employee and not await self.session.get(Employee, employee.id):
                stats['employees_created'] += 1

            # Создать запись о смене
            shift = Shift(
                employee_id=employee.id if employee else None,
                shift_date=shift_data['shift_date'],
                hours_worked=shift_data.get('hours_worked'),
                revenue=shift_data.get('revenue'),
                expenses=shift_data.get('expenses'),
                notes=shift_data.get('notes'),
                imported_from_bot=True,
                bot_shift_id=bot_shift_id
            )
            self.session.add(shift)
            stats['shifts_imported'] += 1

            # Создать транзакцию дохода, если есть выручка
            if shift_data.get('revenue') and shift_data['revenue'] > 0:
                income_category = await self._get_income_category()
                if income_category:
                    transaction = Transaction(
                        date=shift_data['shift_date'],
                        type='income',
                        amount=shift_data['revenue'],
                        category_id=income_category.id,
                        description=f"Доход за смену {shift_data['shift_date']}",
                        source='bot_claude_import',
                        is_confirmed=True,
                        is_kudir_included=True
                    )
                    self.session.add(transaction)
                    stats['transactions_created'] += 1

        await self.session.commit()
        logger.info(f"Import completed: {stats}")
        return stats

    async def import_shift_reports(self, start_date: date, end_date: date) -> int:
        """
        Импортировать отчеты о сменах

        Returns:
            Количество импортированных отчетов
        """
        if not self.sync.is_available():
            return 0

        reports_data = self.sync.get_shift_reports(start_date, end_date)
        imported = 0

        for report_data in reports_data:
            # Проверить, есть ли уже такой отчет
            existing = await self.session.execute(
                select(ShiftReport).where(
                    ShiftReport.date == report_data['date'],
                    ShiftReport.shift == report_data['shift']
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Создать отчет
            report = ShiftReport(
                date=report_data['date'],
                shift=report_data['shift'],
                cash_fact=report_data.get('cash_fact'),
                cash_plan=report_data.get('cash_plan'),
                cashless_fact=report_data.get('cashless_fact'),
                qr_payments=report_data.get('qr_payments'),
                safe=report_data.get('safe'),
                expenses=report_data.get('expenses'),
                workers=report_data.get('workers', []),
                equipment_issues=report_data.get('equipment_issues', []),
                processed=True
            )
            self.session.add(report)
            imported += 1

        await self.session.commit()
        logger.info(f"Imported {imported} shift reports")
        return imported

    async def _get_or_create_employee(self, name: str) -> Employee:
        """Найти или создать сотрудника по имени"""
        # Поиск существующего
        result = await self.session.execute(
            select(Employee).where(Employee.full_name == name)
        )
        employee = result.scalar_one_or_none()

        if not employee:
            # Создать нового
            employee = Employee(
                full_name=name,
                employment_type='OFFER'  # По умолчанию оферта
            )
            self.session.add(employee)
            await self.session.flush()
            logger.info(f"Created new employee: {name}")

        return employee

    async def _get_income_category(self) -> Category:
        """Получить категорию доходов от услуг клуба"""
        result = await self.session.execute(
            select(Category).where(
                Category.name == 'Услуги компьютерного клуба',
                Category.type == 'income'
            )
        )
        return result.scalar_one_or_none()
