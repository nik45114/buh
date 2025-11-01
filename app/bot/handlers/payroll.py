"""
Обработчики для работы с зарплатой
"""
import logging
from datetime import date
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from ..filters import IsOwner
from ...database.db import async_session
from ...database.models import Payroll, Employee
from ...services.payroll_calculator import PayrollCalculator
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("payroll"), IsOwner())
async def cmd_payroll(message: Message):
    """Расчет зарплаты за месяц"""
    # Текущий месяц
    today = date.today()
    year = today.year
    month = today.month - 1 if today.month > 1 else 12
    if month == 12:
        year -= 1

    try:
        await message.answer(f"⏳ Расчет зарплаты за {month:02d}.{year}...")

        async with async_session() as session:
            calculator = PayrollCalculator(session)

            # Рассчитать для всех сотрудников
            payrolls = await calculator.calculate_all_payrolls(year, month)

            if not payrolls:
                await message.answer("❌ Нет данных для расчета")
                return

            # Формирование отчета
            text = f"💰 *Расчет зарплаты за {month:02d}.{year}*\n\n"

            total_gross = 0
            total_ndfl = 0
            total_net = 0
            total_contributions = 0

            for payroll in payrolls:
                text += f"👤 *{payroll['employee_name']}*\n"
                text += f"   Часов: {payroll['total_hours']}\n"
                text += f"   Начислено: {payroll['gross_salary']:,.2f} руб.\n"
                text += f"   НДФЛ: {payroll['ndfl']:,.2f} руб.\n"
                text += f"   К выплате: {payroll['net_salary']:,.2f} руб.\n"
                text += f"   Взносы: {payroll['contributions']['total']:,.2f} руб.\n\n"

                total_gross += float(payroll['gross_salary'])
                total_ndfl += float(payroll['ndfl'])
                total_net += float(payroll['net_salary'])
                total_contributions += float(payroll['contributions']['total'])

            text += f"\n*ИТОГО:*\n"
            text += f"Начислено: {total_gross:,.2f} руб.\n"
            text += f"НДФЛ: {total_ndfl:,.2f} руб.\n"
            text += f"К выплате: {total_net:,.2f} руб.\n"
            text += f"Страховые взносы: {total_contributions:,.2f} руб.\n"
            text += f"*Всего затрат: {total_gross + total_contributions:,.2f} руб.*"

            await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error calculating payroll: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка расчета: {e}")


@router.message(Command("taxes_quarter"), IsOwner())
async def cmd_taxes_quarter(message: Message):
    """Расчет налогов за квартал"""
    today = date.today()
    year = today.year
    quarter = (today.month - 1) // 3 + 1

    if quarter > 1:
        quarter -= 1
    else:
        quarter = 4
        year -= 1

    try:
        await message.answer(f"⏳ Расчет налогов за {quarter} квартал {year}...")

        async with async_session() as session:
            calculator = PayrollCalculator(session)

            # Рассчитать налоги
            tax_data = await calculator.calculate_quarterly_taxes(year, quarter)

            # Получить сроки
            deadlines = await calculator.get_payment_deadlines(year, quarter)

            text = f"💼 *Налоги за {quarter} квартал {year} года*\n\n"

            # НДФЛ
            text += f"*НДФЛ (13%):*\n"
            text += f"   База: {tax_data['ndfl']['base']:,.2f} руб.\n"
            text += f"   Сумма: {tax_data['ndfl']['amount']:,.2f} руб.\n"
            text += f"   Срок: {deadlines['ndfl_deadline'].strftime('%d.%m.%Y')}\n\n"

            # Взносы
            text += f"*Страховые взносы:*\n"
            text += f"   ПФР (22%): {tax_data['contributions']['pension']:,.2f} руб.\n"
            text += f"   ОМС (5.1%): {tax_data['contributions']['medical']:,.2f} руб.\n"
            text += f"   ФСС (2.9%): {tax_data['contributions']['social']:,.2f} руб.\n"
            text += f"   ВНиМ (0.2%): {tax_data['contributions']['injury']:,.2f} руб.\n"
            text += f"   *Итого взносы: {tax_data['contributions']['total']:,.2f} руб.*\n"
            text += f"   Срок: {deadlines['contributions_deadline'].strftime('%d.%m.%Y')}\n\n"

            # Всего
            text += f"*ВСЕГО К УПЛАТЕ: {tax_data['total_taxes']:,.2f} руб.*"

            await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error calculating taxes: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка расчета: {e}")


@router.message(Command("import_shifts"), IsOwner())
async def cmd_import_shifts(message: Message):
    """Импорт смен из Bot_Claude"""
    from ...services.shift_importer import ShiftImporter
    from datetime import timedelta

    try:
        await message.answer("⏳ Импорт смен из Bot_Claude...")

        async with async_session() as session:
            importer = ShiftImporter(session)

            # Импорт за последние 7 дней
            end_date = date.today()
            start_date = end_date - timedelta(days=7)

            stats = await importer.import_shifts(start_date, end_date)

            text = (
                f"✅ *Импорт завершен*\n\n"
                f"Импортировано смен: {stats['shifts_imported']}\n"
                f"Пропущено (дубли): {stats['shifts_skipped']}\n"
                f"Создано сотрудников: {stats['employees_created']}\n"
                f"Создано транзакций: {stats['transactions_created']}"
            )

            await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error importing shifts: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка импорта: {e}")


@router.message(Command("generate_reports"), IsOwner())
async def cmd_generate_reports(message: Message):
    """Генерация всех отчетов"""
    from ...services.report_generators import (
        RSVGenerator, SZVMGenerator, EFS1Generator, USNDeclarationGenerator
    )
    from ...services.payroll_calculator import PayrollCalculator
    from sqlalchemy import func

    today = date.today()
    year = today.year
    quarter = (today.month - 1) // 3 + 1

    if quarter > 1:
        quarter -= 1
    else:
        quarter = 4
        year -= 1

    try:
        await message.answer(f"⏳ Генерация отчетов за {quarter} квартал {year}...")

        async with async_session() as session:
            # Получить данные
            calculator = PayrollCalculator(session)

            # Получить зарплаты
            month_start = (quarter - 1) * 3 + 1
            month_end = month_start + 2

            result = await session.execute(
                select(Payroll).where(
                    Payroll.period_year == year,
                    Payroll.period_month >= month_start,
                    Payroll.period_month <= month_end
                )
            )
            payrolls_db = result.scalars().all()

            # Преобразовать в словари
            payrolls = []
            for p in payrolls_db:
                employee = await session.get(Employee, p.employee_id)
                payrolls.append({
                    'employee_name': employee.full_name if employee else 'Unknown',
                    'gross_salary': p.gross_salary,
                    'contributions': {
                        'pension': p.gross_salary * calculator.PENSION_RATE if p.gross_salary else 0,
                        'medical': p.gross_salary * calculator.MEDICAL_RATE if p.gross_salary else 0,
                        'social': p.gross_salary * calculator.SOCIAL_RATE if p.gross_salary else 0,
                        'injury': p.gross_salary * calculator.INJURY_RATE if p.gross_salary else 0,
                    }
                })

            # Налоги
            tax_data = await calculator.calculate_quarterly_taxes(year, quarter)

            # Генерация РСВ
            rsv_gen = RSVGenerator()
            rsv_path = rsv_gen.generate(year, quarter, payrolls, tax_data)

            # Генерация СЗВ-М (за последний месяц квартала)
            result = await session.execute(select(Employee).where(Employee.fire_date.is_(None)))
            employees = result.scalars().all()
            employees_data = [
                {
                    'full_name': e.full_name,
                    'snils': e.snils,
                    'inn': e.inn
                }
                for e in employees
            ]

            szv_gen = SZVMGenerator()
            szv_path = szv_gen.generate(year, month_end, employees_data)

            # Генерация ЕФС-1
            efs_gen = EFS1Generator()
            employees_full = [
                {
                    'full_name': e.full_name,
                    'position': 'Администратор',
                    'hire_date': e.hire_date,
                    'employment_type': e.employment_type
                }
                for e in employees
            ]
            efs_path = efs_gen.generate(year, quarter, employees_full, [])

            text = (
                f"✅ *Отчеты сгенерированы*\n\n"
                f"📄 РСВ: `{rsv_path}`\n"
                f"📄 СЗВ-М: `{szv_path}`\n"
                f"📄 ЕФС-1: `{efs_path}`\n"
            )

            await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error generating reports: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка генерации: {e}")
