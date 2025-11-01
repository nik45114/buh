"""
Мост между Bot_Claude и Accounting Bot
Автоматическая синхронизация данных между ботами
"""
import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import date, datetime

logger = logging.getLogger(__name__)


class BotBridge:
    """
    Мост для двусторонней связи между Bot_Claude и Accounting Bot

    Функции:
    1. Прием данных от Bot_Claude через webhook
    2. Отправка запросов к Bot_Claude (если у него есть API)
    3. Автоматическая синхронизация
    """

    def __init__(self, bot_claude_url: Optional[str] = None):
        """
        Args:
            bot_claude_url: URL API Bot_Claude (если есть)
                Например: "http://192.168.1.50:8080"
        """
        self.bot_claude_url = bot_claude_url
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def fetch_shift_from_bot_claude(
        self,
        shift_date: date,
        shift_type: str = "evening"
    ) -> Optional[Dict]:
        """
        Получить данные о смене из Bot_Claude

        Работает только если у Bot_Claude есть REST API
        """
        if not self.bot_claude_url:
            logger.warning("Bot_Claude URL not configured")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.bot_claude_url}/api/shift",
                    params={
                        "date": shift_date.isoformat(),
                        "shift": shift_type
                    },
                    timeout=self.timeout
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Fetched shift from Bot_Claude: {shift_date}")
                        return data
                    else:
                        logger.error(f"Bot_Claude returned {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Error fetching from Bot_Claude: {e}")
            return None

    async def notify_bot_claude(
        self,
        event_type: str,
        data: Dict
    ) -> bool:
        """
        Отправить уведомление в Bot_Claude

        Например, когда зарплата рассчитана, отправить уведомление

        Args:
            event_type: Тип события ("payroll_calculated", "tax_paid", etc.)
            data: Данные события
        """
        if not self.bot_claude_url:
            logger.warning("Bot_Claude URL not configured")
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.bot_claude_url}/api/accounting-event",
                    json={
                        "event": event_type,
                        "data": data,
                        "timestamp": datetime.now().isoformat()
                    },
                    timeout=self.timeout
                ) as response:

                    if response.status == 200:
                        logger.info(f"Notified Bot_Claude: {event_type}")
                        return True
                    else:
                        logger.warning(f"Bot_Claude notification failed: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Error notifying Bot_Claude: {e}")
            return False

    def parse_bot_claude_message(self, message_text: str) -> Optional[Dict]:
        """
        Парсинг сообщения от Bot_Claude

        Если Bot_Claude отправляет данные текстом в общий чат,
        эта функция их распарсит

        Пример сообщения:
        "Смена закрыта\\nНаличка: 15000\\nБезнал: 8000\\nQR: 3500"
        """
        try:
            lines = message_text.strip().split('\n')
            data = {}

            for line in lines:
                line = line.strip()

                # Наличка
                if 'наличка' in line.lower() or 'cash' in line.lower():
                    amount = self._extract_number(line)
                    if amount:
                        data['cash_fact'] = amount

                # Безнал
                if 'безнал' in line.lower() or 'cashless' in line.lower():
                    amount = self._extract_number(line)
                    if amount:
                        data['cashless_fact'] = amount

                # QR
                if 'qr' in line.lower():
                    amount = self._extract_number(line)
                    if amount:
                        data['qr_payments'] = amount

                # Сейф
                if 'сейф' in line.lower() or 'safe' in line.lower():
                    amount = self._extract_number(line)
                    if amount:
                        data['safe'] = amount

            if data:
                # Добавить дату и смену
                data['date'] = date.today().isoformat()
                data['shift'] = 'evening'  # или определять из времени
                logger.info(f"Parsed message from Bot_Claude: {data}")
                return data

            return None

        except Exception as e:
            logger.error(f"Error parsing Bot_Claude message: {e}")
            return None

    def _extract_number(self, text: str) -> Optional[float]:
        """Извлечь число из строки"""
        import re
        # Ищем числа с возможным разделителем тысяч
        match = re.search(r'(\d+[\s,]?\d*\.?\d*)', text)
        if match:
            number_str = match.group(1).replace(' ', '').replace(',', '')
            try:
                return float(number_str)
            except ValueError:
                return None
        return None


# Глобальный экземпляр моста
# Настроить URL в зависимости от расположения Bot_Claude
bot_bridge = BotBridge(
    # bot_claude_url="http://192.168.1.50:8080"  # Если на другом сервере
    # bot_claude_url="http://localhost:8080"      # Если на том же сервере
)


# ============= ХЕЛПЕРЫ ДЛЯ ИСПОЛЬЗОВАНИЯ В БОТЕ =============

async def auto_import_shift(shift_date: date = None, shift_type: str = "evening"):
    """
    Автоматически импортировать смену из Bot_Claude

    Использовать в команде /import_shifts
    """
    from ..database.db import async_session
    from ..database.models import Transaction, Category
    from sqlalchemy import select

    if shift_date is None:
        shift_date = date.today()

    # Получить данные из Bot_Claude
    shift_data = await bot_bridge.fetch_shift_from_bot_claude(shift_date, shift_type)

    if not shift_data:
        logger.warning("No shift data received from Bot_Claude")
        return None

    # Сохранить в бухгалтерии
    async with async_session() as session:
        # Найти категорию доходов
        result = await session.execute(
            select(Category).where(
                Category.name == 'Услуги компьютерного клуба',
                Category.type == 'income'
            )
        )
        category = result.scalar_one_or_none()

        if not category:
            logger.error("Income category not found")
            return None

        # Создать транзакцию
        total_revenue = (
            shift_data.get('cash_fact', 0) +
            shift_data.get('cashless_fact', 0) +
            shift_data.get('qr_payments', 0)
        )

        transaction = Transaction(
            date=shift_date,
            type='income',
            amount=total_revenue,
            category_id=category.id,
            description=f"Автоимпорт смена {shift_type} {shift_date}",
            source='bot_claude_api',
            is_confirmed=True,
            is_kudir_included=True
        )

        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)

        logger.info(f"Auto-imported shift: {transaction.id}")
        return transaction


async def notify_payroll_calculated(employee_name: str, amount: float, month: int, year: int):
    """
    Уведомить Bot_Claude о расчете зарплаты

    Использовать после расчета зарплаты
    """
    await bot_bridge.notify_bot_claude(
        event_type="payroll_calculated",
        data={
            "employee": employee_name,
            "amount": amount,
            "month": month,
            "year": year
        }
    )
