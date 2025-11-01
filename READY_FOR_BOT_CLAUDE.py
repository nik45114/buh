"""
ГОТОВЫЙ КОД ДЛЯ BOT_CLAUDE
===========================

⚠️ СКОПИРУЙТЕ ЭТОТ ФАЙЛ НА СЕРВЕР BOT И ДОБАВЬТЕ В ОБРАБОТЧИК ЗАКРЫТИЯ СМЕНЫ
"""

import aiohttp
import asyncio
from datetime import date


# ============= НАСТРОЙКИ (УЖЕ ГОТОВЫ!) =============

ACCOUNTING_SERVER = "64.188.83.12"  # ✅ IP сервера Buh
API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"  # ✅ API ключ


# ============= ФУНКЦИЯ ОТПРАВКИ =============

async def send_to_accounting(
    cash: float,
    cashless: float = 0.0,
    qr: float = 0.0,
    shift_type: str = "evening",
    expenses_list: list = None,
    workers_list: list = None
):
    """
    📤 Отправить данные смены в бухгалтерию

    Args:
        cash: Наличные
        cashless: Безналичные
        qr: QR платежи
        shift_type: "morning" или "evening"
        expenses_list: [{"amount": 500, "description": "Вода"}, ...]
        workers_list: ["Иван", "Мария"]

    Returns:
        True - успешно отправлено
        False - ошибка
    """

    url = f"http://{ACCOUNTING_SERVER}:8000/api/shift-report"

    payload = {
        "date": date.today().isoformat(),
        "shift": shift_type,
        "cash_fact": cash,
        "cashless_fact": cashless,
        "qr_payments": qr,
        "expenses": expenses_list or [],
        "workers": workers_list or []
    }

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"✅ Данные отправлены в бухгалтерию: {result}")
                    return True
                else:
                    error = await resp.text()
                    print(f"❌ Ошибка {resp.status}: {error}")
                    return False

    except Exception as e:
        print(f"❌ Не удалось отправить в бухгалтерию: {e}")
        return False


# ============= СИНХРОННАЯ ВЕРСИЯ (для обычного Python) =============

import requests

def send_to_accounting_sync(cash: float, cashless: float = 0, qr: float = 0):
    """Синхронная версия (без async/await)"""

    url = f"http://{ACCOUNTING_SERVER}:8000/api/shift-report"

    payload = {
        "date": date.today().isoformat(),
        "shift": "evening",
        "cash_fact": cash,
        "cashless_fact": cashless,
        "qr_payments": qr,
        "expenses": [],
        "workers": []
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers={"X-API-Key": API_KEY},
            timeout=10
        )

        if response.status_code == 200:
            print(f"✅ Отправлено: {response.json()}")
            return True
        else:
            print(f"❌ Ошибка {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


# ============= КАК ДОБАВИТЬ В BOT_CLAUDE =============

"""
1. Скопируйте этот файл в папку с Bot_Claude

2. В обработчике закрытия смены добавьте импорт:

    from READY_FOR_BOT_CLAUDE import send_to_accounting


3. После расчета cash/cashless/qr вызовите:

    await send_to_accounting(
        cash=cash_today,
        cashless=card_today,
        qr=qr_today
    )


ПОЛНЫЙ ПРИМЕР:
--------------

from aiogram import Router, F
from aiogram.types import Message
from READY_FOR_BOT_CLAUDE import send_to_accounting  # ← ДОБАВИТЬ

router = Router()

@router.message(F.text == "/close_shift")
async def close_shift(message: Message):
    # Ваш существующий код расчета смены
    cash_today = 15000.0
    card_today = 8000.0
    qr_today = 3500.0

    # НОВЫЙ КОД - отправка в бухгалтерию
    success = await send_to_accounting(
        cash=cash_today,
        cashless=card_today,
        qr=qr_today,
        shift_type="evening",
        workers_list=["Имя работника"]
    )

    if success:
        await message.answer("✅ Смена закрыта и отправлена в бухгалтерию!")
    else:
        await message.answer("⚠️ Смена закрыта, но данные не отправлены")
"""


# ============= ТЕСТ =============

async def test():
    """Тестовая отправка"""
    print("\n" + "="*50)
    print("🧪 ТЕСТ ОТПРАВКИ В БУХГАЛТЕРИЮ")
    print("="*50)

    print(f"\n📡 Сервер: http://{ACCOUNTING_SERVER}:8000")
    print(f"🔑 API Key: {API_KEY[:20]}...")

    print("\n📤 Отправка тестовых данных...")

    success = await send_to_accounting(
        cash=15000.0,
        cashless=8000.0,
        qr=3500.0,
        shift_type="evening",
        expenses_list=[
            {"amount": 500, "description": "Вода"},
            {"amount": 1200, "description": "Канцтовары"}
        ],
        workers_list=["Тестовый Сотрудник"]
    )

    print("\n" + "="*50)
    if success:
        print("✅ ТЕСТ ПРОЙДЕН!")
        print("\n📋 Проверьте в Telegram боте @Buh45114_bot:")
        print("   /today - транзакции за сегодня")
    else:
        print("❌ ТЕСТ ПРОВАЛЕН!")
        print("\n🔍 Проверьте:")
        print("   1. Доступен ли сервер Buh")
        print("   2. Запущен ли бухгалтерский API")
        print("   3. Правильный ли IP адрес")
    print("="*50 + "\n")


if __name__ == "__main__":
    # Запуск теста
    asyncio.run(test())


# ============= ПРИМЕРЫ =============

"""
ПРИМЕР 1: Минимальный
----------------------
await send_to_accounting(cash=15000)


ПРИМЕР 2: Полный
-----------------
await send_to_accounting(
    cash=15000.0,
    cashless=8000.0,
    qr=3500.0,
    shift_type="evening",
    expenses_list=[
        {"amount": 500, "description": "Вода"}
    ],
    workers_list=["Иван"]
)


ПРИМЕР 3: Синхронный (без async)
---------------------------------
send_to_accounting_sync(cash=15000, cashless=8000)


ПРИМЕР 4: С проверкой ошибок
-----------------------------
if await send_to_accounting(cash=15000, cashless=8000):
    print("✅ Успешно!")
else:
    print("❌ Ошибка!")
"""
