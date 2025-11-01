"""
Сервис напоминаний о важных событиях
"""
import logging
from datetime import date, timedelta
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import Reminder, TaxPayment
from ..config import settings

logger = logging.getLogger(__name__)


class ReminderService:
    """Сервис напоминаний"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_reminder(
        self,
        reminder_type: str,
        title: str,
        description: str,
        due_date: date,
        priority: str = 'MEDIUM'
    ) -> Reminder:
        """Создать напоминание"""
        reminder = Reminder(
            reminder_type=reminder_type,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            status='PENDING'
        )
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)

        logger.info(f"Created reminder: {title} (due: {due_date})")
        return reminder

    async def get_due_reminders(self, days_ahead: int = 3) -> List[Reminder]:
        """
        Получить напоминания, которые нужно отправить

        Args:
            days_ahead: За сколько дней до срока напоминать
        """
        threshold_date = date.today() + timedelta(days=days_ahead)

        result = await self.session.execute(
            select(Reminder).where(
                Reminder.status == 'PENDING',
                Reminder.due_date <= threshold_date
            ).order_by(Reminder.due_date, Reminder.priority.desc())
        )

        return result.scalars().all()

    async def send_due_reminders(self):
        """Отправить актуальные напоминания"""
        from aiogram import Bot

        reminders = await self.get_due_reminders(days_ahead=3)

        if not reminders:
            logger.info("No due reminders")
            return

        # Отправка в админ чат
        bot = Bot(token=settings.BOT_TOKEN)

        for reminder in reminders:
            days_left = (reminder.due_date - date.today()).days

            if days_left < 0:
                urgency = "🔴 ПРОСРОЧЕНО"
            elif days_left == 0:
                urgency = "🔴 СЕГОДНЯ"
            elif days_left == 1:
                urgency = "🟠 ЗАВТРА"
            else:
                urgency = f"🟡 Через {days_left} дней"

            text = (
                f"{reminder.priority_emoji} *{urgency}*\n\n"
                f"📌 {reminder.title}\n"
                f"📅 Срок: {reminder.due_date.strftime('%d.%m.%Y')}\n"
            )

            if reminder.description:
                text += f"\n{reminder.description}"

            try:
                await bot.send_message(
                    chat_id=settings.ADMIN_CHAT_ID,
                    text=text,
                    parse_mode="Markdown"
                )

                # Обновить статус
                reminder.status = 'SENT'

            except Exception as e:
                logger.error(f"Error sending reminder {reminder.id}: {e}")

        await self.session.commit()
        await bot.session.close()

        logger.info(f"Sent {len(reminders)} reminders")

    async def check_tax_deadlines(self):
        """Проверить приближающиеся сроки уплаты налогов"""

        # Получить неоплаченные налоги
        result = await self.session.execute(
            select(TaxPayment).where(
                TaxPayment.status != 'PAID',
                TaxPayment.payment_deadline > date.today()
            )
        )
        tax_payments = result.scalars().all()

        for tax in tax_payments:
            days_left = (tax.payment_deadline - date.today()).days

            # Создать напоминание за 7 дней до срока
            if days_left == 7:
                priority = 'HIGH' if tax.tax_amount > 10000 else 'MEDIUM'

                await self.create_reminder(
                    reminder_type='TAX_PAYMENT',
                    title=f'Оплата {tax.tax_type} за {tax.period_name}',
                    description=f'Сумма: {tax.tax_amount:,.2f} руб.',
                    due_date=tax.payment_deadline,
                    priority=priority
                )

            # Критичное напоминание за 1 день
            elif days_left == 1:
                await self.create_reminder(
                    reminder_type='TAX_PAYMENT_URGENT',
                    title=f'СРОЧНО: Оплата {tax.tax_type}',
                    description=f'Сумма: {tax.tax_amount:,.2f} руб.\nСрок ЗАВТРА!',
                    due_date=tax.payment_deadline,
                    priority='CRITICAL'
                )

        await self.session.commit()
        logger.info(f"Checked {len(tax_payments)} tax payment deadlines")

    async def create_payroll_reminders(self, year: int, month: int):
        """Создать напоминания о зарплате"""
        from datetime import date
        from calendar import monthrange

        # Напоминание об авансе (20 числа)
        advance_date = date(year, month, 20)
        await self.create_reminder(
            reminder_type='PAYROLL_ADVANCE',
            title=f'Выплата аванса за {month:02d}.{year}',
            description='Рассчитать и выплатить аванс сотрудникам',
            due_date=advance_date,
            priority='HIGH'
        )

        # Напоминание об окончательном расчете (5 числа следующего месяца)
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        final_date = date(next_year, next_month, 5)

        await self.create_reminder(
            reminder_type='PAYROLL_FINAL',
            title=f'Окончательный расчет ЗП за {month:02d}.{year}',
            description='Рассчитать и выплатить зарплату, уплатить НДФЛ и взносы',
            due_date=final_date,
            priority='CRITICAL'
        )

        await self.session.commit()
        logger.info(f"Created payroll reminders for {month:02d}.{year}")
