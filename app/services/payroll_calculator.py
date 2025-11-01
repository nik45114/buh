"""
Расчет зарплаты и налогов
"""
import logging
from decimal import Decimal
from datetime import date
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database.models import Employee, Shift, Payroll, TaxPayment

logger = logging.getLogger(__name__)


class PayrollCalculator:
    """Калькулятор зарплаты и налогов"""

    # Ставки НДФЛ
    NDFL_RATE = Decimal('0.13')  # 13%

    # Ставки страховых взносов 2024 (для общего тарифа)
    PENSION_RATE = Decimal('0.22')      # 22% пенсионные
    MEDICAL_RATE = Decimal('0.051')     # 5.1% медицинские
    SOCIAL_RATE = Decimal('0.029')      # 2.9% социальные
    INJURY_RATE = Decimal('0.002')      # 0.2% от НС

    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_monthly_payroll(
        self,
        employee_id: int,
        year: int,
        month: int
    ) -> Dict:
        """
        Рассчитать зарплату сотрудника за месяц

        Returns:
            Dict с расчетом зарплаты
        """
        employee = await self.session.get(Employee, employee_id)
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")

        # Получить смены за месяц
        from datetime import datetime
        from calendar import monthrange

        start_date = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        result = await self.session.execute(
            select(func.sum(Shift.hours_worked))
            .where(
                Shift.employee_id == employee_id,
                Shift.shift_date >= start_date,
                Shift.shift_date <= end_date
            )
        )
        total_hours = result.scalar() or Decimal('0')

        # Расчет зарплаты
        if not employee.hourly_rate:
            raise ValueError(f"Employee {employee_id} has no hourly rate")

        gross_salary = total_hours * Decimal(str(employee.hourly_rate))

        # НДФЛ
        ndfl = (gross_salary * self.NDFL_RATE).quantize(Decimal('0.01'))

        # Зарплата к выплате
        net_salary = gross_salary - ndfl

        # Страховые взносы (работодатель платит сверх)
        pension_contrib = (gross_salary * self.PENSION_RATE).quantize(Decimal('0.01'))
        medical_contrib = (gross_salary * self.MEDICAL_RATE).quantize(Decimal('0.01'))
        social_contrib = (gross_salary * self.SOCIAL_RATE).quantize(Decimal('0.01'))
        injury_contrib = (gross_salary * self.INJURY_RATE).quantize(Decimal('0.01'))

        total_contributions = (
            pension_contrib +
            medical_contrib +
            social_contrib +
            injury_contrib
        )

        return {
            'employee_id': employee_id,
            'employee_name': employee.full_name,
            'period_month': month,
            'period_year': year,
            'total_hours': total_hours,
            'hourly_rate': employee.hourly_rate,
            'gross_salary': gross_salary,
            'ndfl': ndfl,
            'net_salary': net_salary,
            'contributions': {
                'pension': pension_contrib,
                'medical': medical_contrib,
                'social': social_contrib,
                'injury': injury_contrib,
                'total': total_contributions
            },
            'total_cost': gross_salary + total_contributions
        }

    async def save_payroll(self, payroll_data: Dict) -> Payroll:
        """Сохранить расчет зарплаты в БД"""

        # Проверить, нет ли уже расчета за этот период
        result = await self.session.execute(
            select(Payroll).where(
                Payroll.employee_id == payroll_data['employee_id'],
                Payroll.period_year == payroll_data['period_year'],
                Payroll.period_month == payroll_data['period_month']
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Обновить существующий
            existing.total_hours = payroll_data['total_hours']
            existing.gross_salary = payroll_data['gross_salary']
            existing.ndfl = payroll_data['ndfl']
            existing.contributions = payroll_data['contributions']['total']
            existing.net_salary = payroll_data['net_salary']
            payroll = existing
        else:
            # Создать новый
            payroll = Payroll(
                employee_id=payroll_data['employee_id'],
                period_month=payroll_data['period_month'],
                period_year=payroll_data['period_year'],
                total_hours=payroll_data['total_hours'],
                gross_salary=payroll_data['gross_salary'],
                ndfl=payroll_data['ndfl'],
                contributions=payroll_data['contributions']['total'],
                net_salary=payroll_data['net_salary'],
                status='DRAFT'
            )
            self.session.add(payroll)

        await self.session.commit()
        await self.session.refresh(payroll)

        logger.info(
            f"Payroll saved for employee {payroll_data['employee_id']} "
            f"for {payroll_data['period_month']}/{payroll_data['period_year']}"
        )

        return payroll

    async def calculate_all_payrolls(self, year: int, month: int) -> List[Dict]:
        """Рассчитать зарплату для всех активных сотрудников за месяц"""

        result = await self.session.execute(
            select(Employee).where(Employee.fire_date.is_(None))
        )
        employees = result.scalars().all()

        payrolls = []
        for employee in employees:
            if not employee.hourly_rate:
                logger.warning(f"Skipping employee {employee.id} - no hourly rate")
                continue

            try:
                payroll_data = await self.calculate_monthly_payroll(
                    employee.id,
                    year,
                    month
                )
                payrolls.append(payroll_data)

                # Сохранить в БД
                await self.save_payroll(payroll_data)

            except Exception as e:
                logger.error(f"Error calculating payroll for employee {employee.id}: {e}")
                continue

        return payrolls

    async def calculate_quarterly_taxes(self, year: int, quarter: int) -> Dict:
        """
        Рассчитать налоги за квартал

        Args:
            year: Год
            quarter: Квартал (1-4)

        Returns:
            Dict с расчетом налогов
        """
        # Определить месяцы квартала
        month_start = (quarter - 1) * 3 + 1
        month_end = month_start + 2

        # Получить все зарплаты за квартал
        result = await self.session.execute(
            select(Payroll).where(
                Payroll.period_year == year,
                Payroll.period_month >= month_start,
                Payroll.period_month <= month_end,
                Payroll.status != 'DRAFT'
            )
        )
        payrolls = result.scalars().all()

        # Суммы
        total_gross = sum(p.gross_salary or Decimal('0') for p in payrolls)
        total_ndfl = sum(p.ndfl or Decimal('0') for p in payrolls)
        total_contributions = sum(p.contributions or Decimal('0') for p in payrolls)

        # Разбивка по типам взносов
        pension = (total_gross * self.PENSION_RATE).quantize(Decimal('0.01'))
        medical = (total_gross * self.MEDICAL_RATE).quantize(Decimal('0.01'))
        social = (total_gross * self.SOCIAL_RATE).quantize(Decimal('0.01'))
        injury = (total_gross * self.INJURY_RATE).quantize(Decimal('0.01'))

        return {
            'year': year,
            'quarter': quarter,
            'total_gross_salary': total_gross,
            'ndfl': {
                'base': total_gross,
                'amount': total_ndfl,
                'rate': float(self.NDFL_RATE)
            },
            'contributions': {
                'pension': pension,
                'medical': medical,
                'social': social,
                'injury': injury,
                'total': pension + medical + social + injury
            },
            'total_taxes': total_ndfl + pension + medical + social + injury
        }

    async def get_payment_deadlines(self, year: int, quarter: int) -> Dict[str, date]:
        """Получить сроки уплаты налогов"""
        from datetime import date

        # НДФЛ платится в месяце, следующем за выплатой (не позднее 28 числа)
        # Взносы - до 28 числа следующего месяца
        # Упрощенно - квартальные сроки

        deadlines = {
            1: date(year, 4, 28),
            2: date(year, 7, 28),
            3: date(year, 10, 28),
            4: date(year + 1, 1, 28)
        }

        quarter_end = deadlines[quarter]

        return {
            'ndfl_deadline': quarter_end,
            'contributions_deadline': quarter_end,
            'quarter_end': quarter_end
        }
