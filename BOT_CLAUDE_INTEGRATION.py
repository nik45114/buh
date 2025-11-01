"""
КОД ДЛЯ BOT_CLAUDE
===================

Скопируйте этот файл на сервер Bot и добавьте в обработчик закрытия смены
"""

import aiohttp
import asyncio
from datetime import date
from typing import Optional


# ============= КОНФИГУРАЦИЯ =============

# IP адрес сервера с бухгалтерией
ACCOUNTING_SERVER = "192.168.1.X"  # ⚠️ ЗАМЕНИТЕ на реальный IP сервера Buh

# Или используйте доменное имя
# ACCOUNTING_SERVER = "buh.local"

# API ключ (тот же, что в /opt/accounting-bot/.env)
API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"


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
    Отправить данные смены в бухгалтерию

    Вызывать после закрытия смены в Bot_Claude

    Args:
        cash: Наличные
        cashless: Безналичные
        qr: QR платежи
        shift_type: "morning" или "evening"
        expenses_list: [{"amount": 500, "description": "Вода"}, ...]
        workers_list: ["Иван", "Мария"]
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


# ============= КАК ДОБАВИТЬ В BOT_CLAUDE =============

"""
ВАРИАНТ 1: Если используете aiogram
------------------------------------

В файле обработчика закрытия смены добавьте импорт:

    from BOT_CLAUDE_INTEGRATION import send_to_accounting


И после успешного закрытия смены вызовите:

    @router.message(Command("close_shift"))
    async def close_shift_handler(message: Message):
        # ... ваш код расчета cash, cashless, qr ...

        # Отправка в бухгалтерию
        await send_to_accounting(
            cash=cash_today,
            cashless=card_today,
            qr=qr_today,
            shift_type="evening",  # или определяйте динамически
            workers_list=["Иван Иванов"]
        )

        await message.answer("✅ Смена закрыта и отправлена в бухгалтерию!")


ВАРИАНТ 2: Если используете python-telegram-bot
------------------------------------------------

    from BOT_CLAUDE_INTEGRATION import send_to_accounting

    def close_shift(update, context):
        # ... ваш код ...

        # Отправка в бухгалтерию
        asyncio.run(send_to_accounting(
            cash=15000,
            cashless=8000,
            qr=3500
        ))

        update.message.reply_text("✅ Смена закрыта!")


ВАРИАНТ 3: Синхронный код (requests)
-------------------------------------

Если не используете async, вот синхронная версия:
"""

import requests

def send_to_accounting_sync(cash: float, cashless: float = 0, qr: float = 0):
    """Синхронная версия"""

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


# ============= ТЕСТ =============

async def test():
    """Тестовая отправка"""
    print("🧪 Тест отправки в бухгалтерию...")

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

    if success:
        print("✅ Тест пройден!")
    else:
        print("❌ Тест провален!")


if __name__ == "__main__":
    # Запуск теста
    asyncio.run(test())


# ============= ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ =============

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
        {"amount": 500, "description": "Вода"},
        {"amount": 1200, "description": "Канцтовары"}
    ],
    workers_list=["Иван Иванов", "Мария Петрова"]
)


ПРИМЕР 3: С проверкой ошибок
------------------------------
success = await send_to_accounting(cash=15000, cashless=8000)

if success:
    await message.answer("✅ Данные отправлены в бухгалтерию!")
else:
    await message.answer("⚠️ Смена закрыта, но данные не отправлены в бухгалтерию")


ПРИМЕР 4: Синхронная версия
----------------------------
send_to_accounting_sync(cash=15000, cashless=8000, qr=3500)
"""

# ============= НАСТРОЙКА СЕРВЕРА =============

"""
1. Узнайте IP адрес сервера Buh:

   На сервере Buh выполните:
   $ ip addr show | grep inet

   Найдите строку вида:
   inet 192.168.1.100/24

   IP адрес: 192.168.1.100


2. Замените в этом файле:

   ACCOUNTING_SERVER = "192.168.1.100"


3. Проверьте доступность с сервера Bot:

   $ curl http://192.168.1.100:8000/health

   Должно вернуть:
   {"status":"ok","service":"accounting-bot-api"}


4. Если firewall блокирует, на сервере Buh разрешите:

   $ sudo ufw allow from <IP_сервера_Bot> to any port 8000


5. Скопируйте этот файл на сервер Bot:

   $ scp BOT_CLAUDE_INTEGRATION.py root@<IP_сервера_Bot>:/path/to/bot_claude/


6. Импортируйте в Bot_Claude и используйте!
"""
