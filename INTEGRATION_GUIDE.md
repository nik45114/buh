# 🔗 Инструкция по интеграции Bot_Claude с Accounting Bot

## Способ 1: HTTP API (Рекомендуется)

### В Bot_Claude добавить код отправки данных после закрытия смены

**Где добавить**: В обработчике закрытия смены Bot_Claude

```python
import aiohttp
import json
from datetime import date

# Настройки бухгалтерского API
ACCOUNTING_API_URL = "http://localhost:8000/api/shift-report"  # Если на том же сервере
# ACCOUNTING_API_URL = "http://buh-server:8000/api/shift-report"  # Если на разных серверах
ACCOUNTING_API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"  # Из .env бухгалтерии


async def send_shift_to_accounting(shift_data: dict):
    """
    Отправить данные о смене в бухгалтерию

    Вызывать после успешного закрытия смены
    """
    # Формирование данных для отправки
    payload = {
        "date": shift_data.get("date", date.today().isoformat()),
        "shift": shift_data.get("shift_type", "evening"),  # "morning" или "evening"
        "cash_fact": float(shift_data.get("cash_fact", 0)),
        "cash_plan": float(shift_data.get("cash_plan", 0)),
        "cashless_fact": float(shift_data.get("cashless_fact", 0)),
        "qr_payments": float(shift_data.get("qr_payments", 0)),
        "safe": float(shift_data.get("safe", 0)),
        "expenses": shift_data.get("expenses", []),  # Список расходов
        "workers": shift_data.get("workers", []),    # Список работников
        "equipment_issues": shift_data.get("equipment_issues", [])
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
                    error = await response.text()
                    print(f"❌ Ошибка отправки в бухгалтерию ({response.status}): {error}")
                    return False

    except Exception as e:
        print(f"❌ Ошибка подключения к бухгалтерии: {e}")
        return False


# ПРИМЕР ИСПОЛЬЗОВАНИЯ:
# После успешного закрытия смены в Bot_Claude добавить:

async def close_shift_handler(message: Message):
    """Обработчик закрытия смены в Bot_Claude"""

    # ... существующий код закрытия смены ...

    # Подготовка данных о смене
    shift_data = {
        "date": "2025-11-01",
        "shift_type": "evening",
        "cash_fact": 15000.00,
        "cash_plan": 14500.00,
        "cashless_fact": 8000.00,
        "qr_payments": 3500.00,
        "safe": 2000.00,
        "expenses": [
            {"amount": 500, "description": "Вода"},
            {"amount": 1200, "description": "Канцтовары"}
        ],
        "workers": ["Иван Иванов", "Мария Петрова"],
        "equipment_issues": ["ПК №5 - тормозит"]
    }

    # Отправка в бухгалтерию
    await send_shift_to_accounting(shift_data)

    # ... продолжение обработки ...
```

---

## Способ 2: Прямое чтение SQLite (Автоматический импорт)

Если Bot_Claude уже записывает смены в SQLite БД, бухгалтерия будет автоматически импортировать их каждую ночь.

### Шаг 1: Убедитесь, что Bot_Claude записывает смены в БД

**Структура таблиц в knowledge.db Bot_Claude должна быть примерно такой:**

```sql
-- В Bot_Claude создать/проверить таблицы:

CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    shift_type TEXT,  -- "morning" или "evening"
    employee_name TEXT,
    hours_worked REAL,
    revenue_cash REAL,
    revenue_cashless REAL,
    revenue_qr REAL,
    expenses REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_name TEXT NOT NULL,
    phone TEXT,
    hourly_rate REAL,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS shift_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    shift_type TEXT,
    cash_fact REAL,
    cash_plan REAL,
    cashless_fact REAL,
    qr_payments REAL,
    safe REAL,
    expenses_json TEXT,  -- JSON список расходов
    workers_list TEXT,   -- Через запятую
    equipment_issues TEXT
);
```

### Шаг 2: Разместить БД в правильном месте

```bash
# Bot_Claude должен создавать БД здесь:
/opt/club_assistant/knowledge.db

# Проверить права доступа:
chmod 644 /opt/club_assistant/knowledge.db
chown <user>:<user> /opt/club_assistant/knowledge.db
```

### Шаг 3: Автоматический импорт уже настроен!

Бухгалтерский бот автоматически импортирует смены каждую ночь в **02:00**.

**Ручной запуск импорта:**
```
/import_shifts
```

---

## Способ 3: Webhook от Bot_Claude

Если Bot_Claude работает как веб-приложение, можно настроить webhook.

```python
# В Bot_Claude добавить после закрытия смены:

import requests

def notify_accounting(shift_data):
    """Отправить webhook в бухгалтерию"""
    try:
        response = requests.post(
            'http://localhost:8000/api/shift-report',
            headers={'X-API-Key': 'YOUR_API_KEY'},
            json=shift_data,
            timeout=5
        )
        return response.status_code == 200
    except:
        return False
```

---

## 🔧 Настройка переменных окружения

### Для Bot_Claude (.env):

```env
# Бухгалтерский API
ACCOUNTING_API_URL=http://localhost:8000
ACCOUNTING_API_KEY=f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c

# Если на разных серверах:
# ACCOUNTING_API_URL=http://192.168.1.100:8000
# или
# ACCOUNTING_API_URL=https://accounting.example.com
```

### Для Accounting Bot (уже настроено):

```env
# В .env бухгалтерии
API_KEY=f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 📊 Формат данных для API

### POST /api/shift-report

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

**Body:**
```json
{
  "date": "2025-11-01",
  "shift": "evening",
  "cash_fact": 15000.00,
  "cash_plan": 14500.00,
  "cashless_fact": 8000.00,
  "qr_payments": 3500.00,
  "safe": 2000.00,
  "expenses": [
    {
      "amount": 500,
      "description": "Вода"
    },
    {
      "amount": 1200,
      "description": "Канцтовары"
    }
  ],
  "workers": ["Иван Иванов", "Мария Петрова"],
  "equipment_issues": ["ПК №5 - тормозит"]
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Shift report processed successfully",
  "transactions_created": 3
}
```

---

## 🧪 Тестирование интеграции

### 1. Проверить доступность API:

```bash
curl http://localhost:8000/health
# Должно вернуть: {"status":"ok","service":"accounting-bot-api"}
```

### 2. Отправить тестовый отчет:

```bash
curl -X POST http://localhost:8000/api/shift-report \
  -H "X-API-Key: f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-11-01",
    "shift": "evening",
    "cash_fact": 15000.00,
    "cashless_fact": 8000.00,
    "qr_payments": 3500.00
  }'
```

### 3. Проверить в Telegram боте:

```
/today        - Посмотреть транзакции за сегодня
/balance      - Проверить баланс
```

---

## 🔐 Безопасность

1. **API Key** должен быть секретным и храниться в `.env`
2. Если боты на разных серверах - используйте HTTPS
3. Рекомендуется ограничить доступ к API по IP:

```nginx
# В nginx
location /api {
    allow 192.168.1.0/24;  # Локальная сеть
    deny all;
    proxy_pass http://localhost:8000;
}
```

---

## 📝 Пример полной интеграции

### Файл: bot_claude/handlers/shift_close.py

```python
from aiogram import Router, F
from aiogram.types import Message
import aiohttp
from datetime import date

router = Router()

ACCOUNTING_API_URL = "http://localhost:8000/api/shift-report"
ACCOUNTING_API_KEY = "f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c"


@router.message(F.text == "/close_shift")
async def close_shift(message: Message):
    """Закрытие смены с отправкой в бухгалтерию"""

    # 1. Собрать данные о смене из Bot_Claude
    shift_data = {
        "date": date.today().isoformat(),
        "shift": "evening",
        "cash_fact": 15000.00,
        "cash_plan": 14500.00,
        "cashless_fact": 8000.00,
        "qr_payments": 3500.00,
        "safe": 2000.00,
        "expenses": [
            {"amount": 500, "description": "Вода"},
            {"amount": 1200, "description": "Канцтовары"}
        ],
        "workers": ["Иван", "Мария"],
        "equipment_issues": []
    }

    # 2. Сохранить в локальную БД Bot_Claude
    # ... ваш код сохранения ...

    # 3. Отправить в бухгалтерию
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ACCOUNTING_API_URL,
                json=shift_data,
                headers={
                    "X-API-Key": ACCOUNTING_API_KEY,
                    "Content-Type": "application/json"
                }
            ) as response:
                if response.status == 200:
                    await message.answer("✅ Смена закрыта и отправлена в бухгалтерию!")
                else:
                    await message.answer(f"⚠️ Смена закрыта, но не отправлена в бухгалтерию (код {response.status})")
    except Exception as e:
        await message.answer(f"⚠️ Смена закрыта локально, но ошибка отправки: {e}")
```

---

## ✅ Проверочный чек-лист

- [ ] Bot_Claude установлен
- [ ] Accounting Bot запущен (`docker-compose ps`)
- [ ] API доступен (`curl http://localhost:8000/health`)
- [ ] API_KEY настроен в обоих ботах
- [ ] Добавлен код отправки данных в Bot_Claude
- [ ] Отправлен тестовый запрос
- [ ] Проверены транзакции в Telegram боте (`/today`)
- [ ] Настроен автоматический импорт (если используется SQLite)

---

## 🆘 Troubleshooting

### Проблема: "Connection refused"
```bash
# Проверить, запущен ли API:
docker-compose ps
docker-compose logs api

# Проверить порт:
netstat -tlnp | grep 8000
```

### Проблема: "Invalid API key"
```bash
# Проверить API_KEY в .env бухгалтерии:
cat /opt/accounting-bot/.env | grep API_KEY

# Должен совпадать с тем, что используется в Bot_Claude
```

### Проблема: "Table not found" (SQLite)
```bash
# Проверить структуру БД Bot_Claude:
sqlite3 /opt/club_assistant/knowledge.db ".schema"
```

---

**Выбирайте любой способ и пишите, помогу настроить!** 🚀
