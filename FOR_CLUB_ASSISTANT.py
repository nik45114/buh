"""
ГОТОВЫЙ КОД ДЛЯ /opt/club_assistant (Bot_Claude)
==================================================

✅ IP и API Key уже настроены
✅ Готово к использованию
✅ Копировать этот файл в /opt/club_assistant/
"""

import aiohttp
import asyncio
from datetime import date
from typing import Optional, List, Dict


# ============= НАСТРОЙКИ (УЖЕ ГОТОВЫ!) =============

ACCOUNTING_API_URL = "http://64.188.83.12:8000"
API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"


# ============= ОСНОВНАЯ ФУНКЦИЯ =============

async def send_to_accounting(
    cash: float,
    cashless: float = 0.0,
    qr: float = 0.0,
    shift_type: str = "evening",
    expenses_list: Optional[List[Dict]] = None,
    workers_list: Optional[List[str]] = None
) -> bool:
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

    Пример использования:
        await send_to_accounting(
            cash=15000,
            cashless=8000,
            qr=3500,
            shift_type="evening",
            workers_list=["Иван Иванов"]
        )
    """

    url = f"{ACCOUNTING_API_URL}/api/shift-report"

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


# ============= КАК ИСПОЛЬЗОВАТЬ В CLUB_ASSISTANT =============

"""
ШАГ 1: Найти обработчик закрытия смены
---------------------------------------

Найдите в /opt/club_assistant/ файл, где обрабатывается закрытие смены.
Обычно это:
- handlers/shift.py
- handlers/admin.py
- handlers/close_shift.py
или похожий файл


ШАГ 2: Добавить импорт
-----------------------

В начале файла добавьте:

    from FOR_CLUB_ASSISTANT import send_to_accounting


ШАГ 3: Добавить вызов после закрытия смены
--------------------------------------------

Найдите функцию закрытия смены, например:

    @router.message(Command("close_shift"))
    async def close_shift_handler(message: Message):
        # Существующий код расчета смены
        cash_today = calculate_cash()
        card_today = calculate_card()
        qr_today = calculate_qr()

        # ДОБАВИТЬ ЭТО:
        await send_to_accounting(
            cash=cash_today,
            cashless=card_today,
            qr=qr_today,
            shift_type="evening",  # или определять динамически
            workers_list=["Имя сотрудника"]  # если есть данные
        )

        await message.answer("✅ Смена закрыта и отправлена в бухгалтерию!")


ПОЛНЫЙ ПРИМЕР:
--------------
"""

# Пример полного обработчика с интеграцией
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from FOR_CLUB_ASSISTANT import send_to_accounting  # ← ИМПОРТ

router = Router()

@router.message(Command("close_shift"))
async def close_shift(message: Message, session):
    # Ваш существующий код
    cash_total = await get_cash_from_db(session)
    card_total = await get_card_from_db(session)
    qr_total = await get_qr_from_db(session)

    # Расходы (если есть)
    expenses = await get_expenses_from_db(session)
    expenses_list = [
        {"amount": e.amount, "description": e.description}
        for e in expenses
    ]

    # Работники смены (если есть)
    workers = await get_workers_from_db(session)
    workers_list = [w.name for w in workers]

    # ОТПРАВКА В БУХГАЛТЕРИЮ
    success = await send_to_accounting(
        cash=cash_total,
        cashless=card_total,
        qr=qr_total,
        shift_type="evening",
        expenses_list=expenses_list,
        workers_list=workers_list
    )

    if success:
        await message.answer("✅ Смена закрыта и данные отправлены в бухгалтерию!")
    else:
        await message.answer("⚠️ Смена закрыта, но не удалось отправить данные в бухгалтерию")
"""


# ============= ТЕСТ =============

async def test():
    """Тестовая отправка для проверки работоспособности"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ ИНТЕГРАЦИИ /opt/club_assistant → БУХГАЛТЕРИЯ")
    print("="*60)

    print(f"\n📡 API Сервер: {ACCOUNTING_API_URL}")
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

    print("\n" + "="*60)
    if success:
        print("✅ ТЕСТ ПРОЙДЕН!")
        print("\n📋 Проверьте в Telegram боте @Buh45114_bot:")
        print("   /today - транзакции за сегодня")
        print("   /balance - текущий баланс")
    else:
        print("❌ ТЕСТ ПРОВАЛЕН!")
        print("\n🔍 Проверьте:")
        print("   1. Доступен ли сервер 64.188.83.12")
        print("   2. Запущен ли бухгалтерский API")
        print("   3. Правильный ли API ключ")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Запуск теста
    print("Для теста запустите:")
    print("cd /opt/club_assistant")
    print("python3 FOR_CLUB_ASSISTANT.py")
    print()
    asyncio.run(test())


# ============= ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ =============

"""
ПРИМЕР 1: Минимальный (только наличка)
---------------------------------------
await send_to_accounting(cash=15000)


ПРИМЕР 2: Все способы оплаты
------------------------------
await send_to_accounting(
    cash=15000,
    cashless=8000,
    qr=3500
)


ПРИМЕР 3: С расходами
----------------------
await send_to_accounting(
    cash=15000,
    cashless=8000,
    expenses_list=[
        {"amount": 500, "description": "Вода 5л x10"},
        {"amount": 1200, "description": "Канцтовары"},
        {"amount": 300, "description": "Чистящие средства"}
    ]
)


ПРИМЕР 4: Полный (все данные)
-------------------------------
await send_to_accounting(
    cash=15000.0,
    cashless=8000.0,
    qr=3500.0,
    shift_type="evening",
    expenses_list=[
        {"amount": 500, "description": "Вода"},
        {"amount": 1200, "description": "Канцтовары"}
    ],
    workers_list=["Иван Иванов", "Мария Петрова"]
)


ПРИМЕР 5: С проверкой ошибок
------------------------------
success = await send_to_accounting(cash=15000, cashless=8000)

if success:
    print("✅ Данные отправлены!")
else:
    print("❌ Ошибка отправки!")
    # Можно отправить уведомление администратору
"""
