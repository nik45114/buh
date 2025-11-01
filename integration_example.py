"""
Пример интеграции Bot_Claude с Accounting Bot
Добавьте этот код в обработчик закрытия смены вашего основного бота
"""

import aiohttp
import asyncio
from datetime import date
from typing import Optional, Dict, List


# ============= НАСТРОЙКИ =============
ACCOUNTING_API_URL = "http://localhost:8000/api/shift-report"
# Если боты на разных серверах, укажите IP:
# ACCOUNTING_API_URL = "http://192.168.1.100:8000/api/shift-report"

# API ключ из .env бухгалтерского бота
ACCOUNTING_API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"


# ============= ФУНКЦИЯ ОТПРАВКИ =============
async def send_shift_to_accounting(
    shift_date: str,              # "2025-11-01"
    shift_type: str,              # "morning" или "evening"
    cash_fact: float,             # Наличные по факту
    cash_plan: float = None,      # Наличные по плану (опционально)
    cashless_fact: float = 0.0,   # Безнал
    qr_payments: float = 0.0,     # QR платежи
    safe: float = 0.0,            # В сейф
    expenses: List[Dict] = None,  # Список расходов
    workers: List[str] = None,    # Список работников
    equipment_issues: List[str] = None  # Проблемы с оборудованием
) -> bool:
    """
    Отправить данные о смене в бухгалтерский бот

    Returns:
        True - успешно отправлено
        False - ошибка отправки
    """
    payload = {
        "date": shift_date,
        "shift": shift_type,
        "cash_fact": cash_fact,
        "cash_plan": cash_plan or cash_fact,
        "cashless_fact": cashless_fact,
        "qr_payments": qr_payments,
        "safe": safe,
        "expenses": expenses or [],
        "workers": workers or [],
        "equipment_issues": equipment_issues or []
    }

    headers = {
        "X-API-Key": ACCOUNTING_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ACCOUNTING_API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:

                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Смена отправлена в бухгалтерию: {result}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка {response.status}: {error_text}")
                    return False

    except aiohttp.ClientError as e:
        print(f"❌ Ошибка подключения к бухгалтерии: {e}")
        return False
    except Exception as e:
        print(f"❌ Неизвестная ошибка: {e}")
        return False


# ============= ПРИМЕР ИСПОЛЬЗОВАНИЯ =============

# Вариант 1: Простейший (только наличка)
async def example_simple():
    """Минимальный пример"""
    success = await send_shift_to_accounting(
        shift_date="2025-11-01",
        shift_type="evening",
        cash_fact=15000.00
    )

    if success:
        print("Данные отправлены!")
    else:
        print("Не удалось отправить данные")


# Вариант 2: Полный (все данные)
async def example_full():
    """Полный пример со всеми данными"""
    success = await send_shift_to_accounting(
        shift_date="2025-11-01",
        shift_type="evening",
        cash_fact=15000.00,
        cash_plan=14500.00,
        cashless_fact=8000.00,
        qr_payments=3500.00,
        safe=2000.00,
        expenses=[
            {"amount": 500, "description": "Вода"},
            {"amount": 1200, "description": "Канцтовары"},
            {"amount": 300, "description": "Чистящие средства"}
        ],
        workers=["Иван Иванов", "Мария Петрова"],
        equipment_issues=["ПК №5 - тормозит", "Кресло №3 - сломано"]
    )

    if success:
        print("✅ Смена успешно отправлена в бухгалтерию!")


# ============= КАК ДОБАВИТЬ В BOT_CLAUDE =============

"""
В вашем основном боте (Bot_Claude) в обработчике закрытия смены добавьте:

from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.text.startswith("/close_shift"))
async def close_shift_handler(message: Message):
    '''Закрытие смены'''

    # ... ваш существующий код сбора данных о смене ...

    # Получить данные из вашей БД или переменных
    cash_today = 15000.00  # Ваша переменная
    cashless_today = 8000.00  # Ваша переменная
    qr_today = 3500.00  # Ваша переменная

    # Отправить в бухгалтерию
    success = await send_shift_to_accounting(
        shift_date=date.today().isoformat(),
        shift_type="evening",  # или "morning"
        cash_fact=cash_today,
        cashless_fact=cashless_today,
        qr_payments=qr_today,
        workers=["Имя сотрудника"],  # Список работников смены
        expenses=[]  # Расходы если есть
    )

    if success:
        await message.answer("✅ Смена закрыта и отправлена в бухгалтерию!")
    else:
        await message.answer("⚠️ Смена закрыта локально, но не отправлена в бухгалтерию")
"""


# ============= ВАРИАНТ БЕЗ ASYNC (для обычного Python) =============

import requests

def send_shift_sync(shift_date: str, shift_type: str, cash_fact: float, **kwargs):
    """Синхронная версия (без async/await)"""

    payload = {
        "date": shift_date,
        "shift": shift_type,
        "cash_fact": cash_fact,
        "cash_plan": kwargs.get("cash_plan", cash_fact),
        "cashless_fact": kwargs.get("cashless_fact", 0.0),
        "qr_payments": kwargs.get("qr_payments", 0.0),
        "safe": kwargs.get("safe", 0.0),
        "expenses": kwargs.get("expenses", []),
        "workers": kwargs.get("workers", []),
        "equipment_issues": kwargs.get("equipment_issues", [])
    }

    try:
        response = requests.post(
            ACCOUNTING_API_URL,
            json=payload,
            headers={
                "X-API-Key": ACCOUNTING_API_KEY,
                "Content-Type": "application/json"
            },
            timeout=10
        )

        if response.status_code == 200:
            print(f"✅ Успешно: {response.json()}")
            return True
        else:
            print(f"❌ Ошибка {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


# Пример использования синхронной версии:
def example_sync():
    send_shift_sync(
        shift_date="2025-11-01",
        shift_type="evening",
        cash_fact=15000.00,
        cashless_fact=8000.00
    )


# ============= ЗАПУСК ПРИМЕРОВ =============
if __name__ == "__main__":
    # Тест async версии
    print("=== Тест async версии ===")
    asyncio.run(example_simple())

    print("\n=== Тест полной версии ===")
    asyncio.run(example_full())

    # Тест sync версии
    print("\n=== Тест sync версии ===")
    example_sync()
