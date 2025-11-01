"""
Интеграция со СБИС ОФД
======================

Автоматический контроль смен через онлайн-кассу:
- Получение данных с кассы через СБИС ОФД API
- Сравнение факта с кассой
- Выявление расхождений
- Уведомления о проблемах
"""

import logging
import aiohttp
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


class SbisOFD:
    """
    Клиент для работы с СБИС ОФД API

    Документация API: https://sbis.ru/ofd/api
    """

    def __init__(self, api_token: str, inn: str):
        """
        Args:
            api_token: Токен доступа к СБИС ОФД API
            inn: ИНН организации
        """
        self.api_token = api_token
        self.inn = inn
        self.base_url = "https://api.sbis.ru/ofd/v1"
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def _request(self, method: str, endpoint: str, params: Dict = None, json_data: Dict = None) -> Dict:
        """Выполнить запрос к API"""
        url = f"{self.base_url}/{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_data
                ) as response:

                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"SBIS OFD API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error calling SBIS OFD API: {e}")
            return None

    async def get_shift_receipts(
        self,
        shift_date: date,
        kkt_number: Optional[str] = None
    ) -> Optional[List[Dict]]:
        """
        Получить все чеки за смену

        Args:
            shift_date: Дата смены
            kkt_number: Номер ККТ (опционально, если касс несколько)

        Returns:
            Список чеков или None при ошибке
        """
        params = {
            "inn": self.inn,
            "date_from": shift_date.isoformat(),
            "date_to": shift_date.isoformat()
        }

        if kkt_number:
            params["kkt_number"] = kkt_number

        data = await self._request("GET", "receipts", params=params)

        if data and "receipts" in data:
            return data["receipts"]

        return None

    async def get_shift_totals(
        self,
        shift_date: date,
        kkt_number: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Получить итоги смены (Z-отчет)

        Args:
            shift_date: Дата смены
            kkt_number: Номер ККТ

        Returns:
            Данные Z-отчета:
            {
                "cash": 15000.00,      # Наличные
                "cashless": 8000.00,   # Безналичные
                "total": 23000.00,     # Итого
                "receipts_count": 150, # Количество чеков
                "shift_number": 123,   # Номер смены
                "opened_at": "2025-01-15T08:00:00",
                "closed_at": "2025-01-15T20:00:00"
            }
        """
        params = {
            "inn": self.inn,
            "date": shift_date.isoformat()
        }

        if kkt_number:
            params["kkt_number"] = kkt_number

        data = await self._request("GET", "shift-report", params=params)

        if not data:
            return None

        # Парсинг ответа СБИС
        return {
            "cash": Decimal(str(data.get("cash", 0))),
            "cashless": Decimal(str(data.get("cashless", 0))),
            "total": Decimal(str(data.get("total", 0))),
            "receipts_count": data.get("receipts_count", 0),
            "shift_number": data.get("shift_number"),
            "opened_at": data.get("opened_at"),
            "closed_at": data.get("closed_at")
        }

    async def get_receipts_by_payment_type(
        self,
        shift_date: date,
        kkt_number: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Получить разбивку чеков по типам оплаты

        Returns:
            {
                "cash": 15000.00,
                "cashless": 8000.00,
                "prepaid": 0.00,
                "credit": 0.00
            }
        """
        receipts = await self.get_shift_receipts(shift_date, kkt_number)

        if not receipts:
            return None

        totals = {
            "cash": Decimal("0"),
            "cashless": Decimal("0"),
            "prepaid": Decimal("0"),
            "credit": Decimal("0")
        }

        for receipt in receipts:
            # Тип операции: приход/расход
            if receipt.get("operation_type") != "income":
                continue

            # Разбивка по типам оплаты
            payments = receipt.get("payments", [])
            for payment in payments:
                payment_type = payment.get("type")
                amount = Decimal(str(payment.get("amount", 0)))

                if payment_type == 0:  # Наличные
                    totals["cash"] += amount
                elif payment_type == 1:  # Безналичные
                    totals["cashless"] += amount
                elif payment_type == 2:  # Предоплата
                    totals["prepaid"] += amount
                elif payment_type == 3:  # Кредит
                    totals["credit"] += amount

        return totals

    async def check_shift_closed(
        self,
        shift_date: date,
        kkt_number: Optional[str] = None
    ) -> bool:
        """
        Проверить, закрыта ли смена на кассе

        Returns:
            True - смена закрыта
            False - смена не закрыта или ошибка
        """
        shift_data = await self.get_shift_totals(shift_date, kkt_number)

        if not shift_data:
            return False

        # Смена закрыта, если есть closed_at
        return shift_data.get("closed_at") is not None


class ShiftValidator:
    """
    Валидатор смен - сравнение факта с кассой
    """

    def __init__(self, sbis_client: SbisOFD):
        self.sbis = sbis_client
        self.tolerance = Decimal("100")  # Допустимое расхождение: 100 рублей

    async def validate_shift(
        self,
        shift_date: date,
        fact_cash: Decimal,
        fact_cashless: Decimal,
        fact_qr: Decimal = Decimal("0"),
        kkt_number: Optional[str] = None
    ) -> Dict:
        """
        Проверить смену на расхождения

        Args:
            shift_date: Дата смены
            fact_cash: Фактические наличные (из Bot_Claude)
            fact_cashless: Фактический безнал (из Bot_Claude)
            fact_qr: Фактические QR платежи (из Bot_Claude)
            kkt_number: Номер ККТ

        Returns:
            {
                "status": "ok" | "warning" | "error",
                "is_closed": True/False,
                "discrepancies": {
                    "cash": {"fact": 15000, "kkt": 14900, "diff": 100},
                    "cashless": {"fact": 8000, "kkt": 8000, "diff": 0},
                    "total": {"fact": 23000, "kkt": 22900, "diff": 100}
                },
                "message": "Расхождение в наличных: 100 ₽"
            }
        """
        # Получить данные с кассы
        kkt_data = await self.sbis.get_shift_totals(shift_date, kkt_number)

        if not kkt_data:
            return {
                "status": "error",
                "is_closed": False,
                "message": "Не удалось получить данные с кассы. Проверьте подключение к СБИС ОФД."
            }

        # Проверить, закрыта ли смена
        is_closed = kkt_data.get("closed_at") is not None

        if not is_closed:
            return {
                "status": "warning",
                "is_closed": False,
                "message": "⚠️ Смена на кассе НЕ ЗАКРЫТА! Закройте смену на кассе."
            }

        # Данные с кассы
        kkt_cash = kkt_data["cash"]
        kkt_cashless = kkt_data["cashless"]
        kkt_total = kkt_data["total"]

        # Фактические данные
        fact_total = fact_cash + fact_cashless + fact_qr

        # Расхождения
        diff_cash = fact_cash - kkt_cash
        diff_cashless = (fact_cashless + fact_qr) - kkt_cashless  # QR идет как безнал
        diff_total = fact_total - kkt_total

        discrepancies = {
            "cash": {
                "fact": float(fact_cash),
                "kkt": float(kkt_cash),
                "diff": float(diff_cash)
            },
            "cashless": {
                "fact": float(fact_cashless + fact_qr),
                "kkt": float(kkt_cashless),
                "diff": float(diff_cashless)
            },
            "total": {
                "fact": float(fact_total),
                "kkt": float(kkt_total),
                "diff": float(diff_total)
            }
        }

        # Проверить расхождения
        issues = []

        if abs(diff_cash) > self.tolerance:
            issues.append(f"Наличные: {diff_cash:+,.0f} ₽")

        if abs(diff_cashless) > self.tolerance:
            issues.append(f"Безнал: {diff_cashless:+,.0f} ₽")

        if abs(diff_total) > self.tolerance:
            issues.append(f"Итого: {diff_total:+,.0f} ₽")

        # Определить статус
        if issues:
            status = "warning"
            message = "⚠️ РАСХОЖДЕНИЯ:\n" + "\n".join(f"• {issue}" for issue in issues)
        else:
            status = "ok"
            message = "✅ Смена совпадает с кассой"

        return {
            "status": status,
            "is_closed": is_closed,
            "discrepancies": discrepancies,
            "message": message,
            "kkt_shift_number": kkt_data.get("shift_number"),
            "kkt_receipts_count": kkt_data.get("receipts_count")
        }

    async def get_validation_report(
        self,
        shift_date: date,
        fact_cash: Decimal,
        fact_cashless: Decimal,
        fact_qr: Decimal = Decimal("0"),
        kkt_number: Optional[str] = None
    ) -> str:
        """
        Получить текстовый отчет о проверке смены

        Returns:
            Форматированный текст для отправки в Telegram
        """
        result = await self.validate_shift(
            shift_date, fact_cash, fact_cashless, fact_qr, kkt_number
        )

        if result["status"] == "error":
            return f"❌ {result['message']}"

        disc = result["discrepancies"]

        report = f"""
📊 СВЕРКА СМЕНЫ С КАССОЙ
{'='*40}

📅 Дата: {shift_date.strftime('%d.%m.%Y')}
{'✅ Смена закрыта' if result['is_closed'] else '⚠️ Смена НЕ закрыта'}
🧾 Чеков: {result.get('kkt_receipts_count', 'N/A')}
📋 Смена №: {result.get('kkt_shift_number', 'N/A')}

{'='*40}

💰 НАЛИЧНЫЕ:
   Факт:  {disc['cash']['fact']:>12,.2f} ₽
   Касса: {disc['cash']['kkt']:>12,.2f} ₽
   Разница: {disc['cash']['diff']:>10,.2f} ₽

💳 БЕЗНАЛ:
   Факт:  {disc['cashless']['fact']:>12,.2f} ₽
   Касса: {disc['cashless']['kkt']:>12,.2f} ₽
   Разница: {disc['cashless']['diff']:>10,.2f} ₽

📊 ИТОГО:
   Факт:  {disc['total']['fact']:>12,.2f} ₽
   Касса: {disc['total']['kkt']:>12,.2f} ₽
   Разница: {disc['total']['diff']:>10,.2f} ₽

{'='*40}

{result['message']}
"""

        return report.strip()


# ============= INTEGRATION WITH BOT =============

async def validate_shift_with_ofd(
    shift_date: date,
    fact_cash: float,
    fact_cashless: float,
    fact_qr: float = 0.0,
    api_token: Optional[str] = None,
    inn: Optional[str] = None,
    kkt_number: Optional[str] = None
) -> Dict:
    """
    Хелпер для проверки смены через СБИС ОФД

    Использовать в обработчике закрытия смены

    Args:
        shift_date: Дата смены
        fact_cash: Фактические наличные
        fact_cashless: Фактический безнал
        fact_qr: Фактические QR платежи
        api_token: Токен СБИС ОФД (из переменных окружения если не указан)
        inn: ИНН организации (из переменных окружения если не указан)
        kkt_number: Номер ККТ

    Returns:
        Результат валидации
    """
    import os

    # Получить настройки из переменных окружения
    if not api_token:
        api_token = os.getenv("SBIS_OFD_TOKEN")

    if not inn:
        inn = os.getenv("COMPANY_INN")

    if not api_token or not inn:
        logger.error("SBIS OFD credentials not configured")
        return {
            "status": "error",
            "message": "СБИС ОФД не настроен. Добавьте SBIS_OFD_TOKEN и COMPANY_INN в .env"
        }

    # Создать клиентов
    sbis = SbisOFD(api_token, inn)
    validator = ShiftValidator(sbis)

    # Проверить смену
    result = await validator.validate_shift(
        shift_date,
        Decimal(str(fact_cash)),
        Decimal(str(fact_cashless)),
        Decimal(str(fact_qr)),
        kkt_number
    )

    return result


async def get_shift_validation_report(
    shift_date: date,
    fact_cash: float,
    fact_cashless: float,
    fact_qr: float = 0.0,
    api_token: Optional[str] = None,
    inn: Optional[str] = None,
    kkt_number: Optional[str] = None
) -> str:
    """
    Получить текстовый отчет о сверке смены

    Returns:
        Форматированный текст для Telegram
    """
    import os

    if not api_token:
        api_token = os.getenv("SBIS_OFD_TOKEN")

    if not inn:
        inn = os.getenv("COMPANY_INN")

    if not api_token or not inn:
        return "❌ СБИС ОФД не настроен"

    sbis = SbisOFD(api_token, inn)
    validator = ShiftValidator(sbis)

    report = await validator.get_validation_report(
        shift_date,
        Decimal(str(fact_cash)),
        Decimal(str(fact_cashless)),
        Decimal(str(fact_qr)),
        kkt_number
    )

    return report


# ============= ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ =============

"""
ПРИМЕР 1: Проверка смены при закрытии
--------------------------------------

from app.services.sbis_ofd import validate_shift_with_ofd
from datetime import date

# В обработчике закрытия смены
validation = await validate_shift_with_ofd(
    shift_date=date.today(),
    fact_cash=15000.0,
    fact_cashless=8000.0,
    fact_qr=3500.0
)

if validation["status"] == "warning":
    await message.answer(f"⚠️ {validation['message']}")
elif validation["status"] == "ok":
    await message.answer("✅ Смена совпадает с кассой")


ПРИМЕР 2: Получить полный отчет
--------------------------------

from app.services.sbis_ofd import get_shift_validation_report

report = await get_shift_validation_report(
    shift_date=date.today(),
    fact_cash=15000.0,
    fact_cashless=8000.0,
    fact_qr=3500.0
)

await message.answer(report)


ПРИМЕР 3: Использование в команде /check_shift
-----------------------------------------------

@router.message(Command("check_shift"))
async def check_shift_handler(message: Message):
    # Получить данные смены из БД
    shift = await get_today_shift()

    # Проверить с СБИС ОФД
    report = await get_shift_validation_report(
        shift_date=date.today(),
        fact_cash=shift.cash,
        fact_cashless=shift.cashless,
        fact_qr=shift.qr
    )

    await message.answer(report)


ПРИМЕР 4: Автоматическая проверка при закрытии
-----------------------------------------------

@router.message(Command("close_shift"))
async def close_shift(message: Message):
    # Закрыть смену
    cash, cashless, qr = await close_shift_in_db()

    # Отправить в бухгалтерию
    await send_to_accounting(cash, cashless, qr)

    # ПРОВЕРИТЬ С КАССОЙ
    validation = await validate_shift_with_ofd(
        date.today(), cash, cashless, qr
    )

    if validation["status"] == "ok":
        await message.answer("✅ Смена закрыта и совпадает с кассой")
    else:
        await message.answer(
            f"⚠️ Смена закрыта, но есть расхождения:\n\n{validation['message']}"
        )
"""
