#!/bin/bash

# Скрипт для обновления accounting-bot до последней версии

set -e

echo "🔄 Обновление accounting-bot..."

# Проверяем наличие docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose не найден. Установите Docker Compose."
    exit 1
fi

# Определяем какой файл compose использовать
COMPOSE_FILE="docker-compose.prod.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    COMPOSE_FILE="docker-compose.yml"
fi

echo "📦 Используется конфигурация: $COMPOSE_FILE"

# Останавливаем контейнеры
echo "⏸️  Остановка контейнеров..."
docker-compose -f "$COMPOSE_FILE" down

# Подтягиваем последние образы
echo "⬇️  Загрузка последних образов..."
docker-compose -f "$COMPOSE_FILE" pull

# Запускаем обновленные контейнеры
echo "🚀 Запуск обновленных контейнеров..."
docker-compose -f "$COMPOSE_FILE" up -d

# Проверяем статус
echo ""
echo "✅ Обновление завершено!"
echo ""
echo "📊 Статус контейнеров:"
docker-compose -f "$COMPOSE_FILE" ps

echo ""
echo "📝 Логи доступны командой:"
echo "   docker-compose -f $COMPOSE_FILE logs -f"
