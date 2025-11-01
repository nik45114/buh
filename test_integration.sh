#!/bin/bash

# Тест интеграции Bot_Claude → Accounting Bot

echo "🧪 Тест интеграции бухгалтерского API"
echo "======================================"
echo ""

# 1. Проверка доступности API
echo "1️⃣ Проверка доступности API..."
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q "ok"; then
    echo "✅ API доступен: $HEALTH"
else
    echo "❌ API недоступен!"
    exit 1
fi
echo ""

# 2. Отправка тестового отчета о смене
echo "2️⃣ Отправка тестового отчета о смене..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/shift-report \
  -H "X-API-Key: f632d94a0815ca53930f2168e5cf1a741ce3e67841e5786f696c64b8d8e6895c" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-11-01",
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
    "workers": ["Иван Иванов", "Мария Петрова"],
    "equipment_issues": ["ПК №5 - тормозит"]
  }')

echo "Ответ API: $RESPONSE"

if echo "$RESPONSE" | grep -q "success"; then
    echo "✅ Отчет о смене успешно отправлен!"
else
    echo "❌ Ошибка отправки отчета"
    exit 1
fi
echo ""

# 3. Проверка созданных транзакций
echo "3️⃣ Проверка созданных транзакций в БД..."
docker-compose exec -T postgres psql -U accounting -d accounting -c "
SELECT
    id,
    date,
    type,
    amount,
    description,
    source
FROM transactions
WHERE date = '2025-11-01'
ORDER BY id DESC
LIMIT 5;
" 2>/dev/null || echo "⚠️ Не удалось проверить БД"
echo ""

# 4. Проверка shift_reports
echo "4️⃣ Проверка shift_reports..."
docker-compose exec -T postgres psql -U accounting -d accounting -c "
SELECT
    id,
    date,
    shift,
    cash_fact,
    cashless_fact,
    qr_payments,
    processed
FROM shift_reports
WHERE date = '2025-11-01'
ORDER BY id DESC
LIMIT 3;
" 2>/dev/null || echo "⚠️ Не удалось проверить БД"
echo ""

echo "======================================"
echo "✅ Тест завершен!"
echo ""
echo "📋 Для проверки в Telegram боте отправьте:"
echo "   /today      - Транзакции за сегодня"
echo "   /balance    - Текущий баланс"
echo ""
