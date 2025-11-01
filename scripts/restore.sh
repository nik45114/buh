#!/bin/bash
set -e

# ═══════════════════════════════════════════════════
# Восстановление базы данных из бэкапа
# ═══════════════════════════════════════════════════

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Загрузка переменных
ENV_FILE="/opt/accounting-bot/.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' $ENV_FILE | xargs)
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

BACKUP_DIR="/opt/accounting-bot/backups"

# Функция логирования
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Проверка аргументов
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    echo "Daily backups:"
    ls -lh $BACKUP_DIR/daily/*.sql.gz 2>/dev/null | tail -5
    echo ""
    echo "Weekly backups:"
    ls -lh $BACKUP_DIR/weekly/*.sql.gz 2>/dev/null | tail -5
    exit 1
fi

BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ]; then
    error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Подтверждение
echo -e "${YELLOW}⚠️  WARNING: This will DROP and recreate the database!${NC}"
echo "Backup file: $BACKUP_FILE"
echo "Database: $DB_NAME"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

log "🔄 Starting database restore..."

# Распаковываем если нужно
if [[ $BACKUP_FILE == *.gz ]]; then
    log "📦 Decompressing backup..."
    TEMP_SQL="/tmp/restore_$(date +%s).sql"
    gunzip -c $BACKUP_FILE > $TEMP_SQL
else
    TEMP_SQL=$BACKUP_FILE
fi

# Останавливаем приложения
log "⏸️  Stopping services..."
docker-compose -f /opt/accounting-bot/docker-compose.yml stop bot api 2>/dev/null || true

# Пересоздаем БД
log "🗑️  Dropping database..."
docker exec accounting_postgres psql -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true

log "🆕 Creating database..."
docker exec accounting_postgres psql -U $DB_USER -d postgres -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || true

# Восстанавливаем данные
log "📥 Restoring data..."
if cat $TEMP_SQL | docker exec -i accounting_postgres psql -U $DB_USER -d $DB_NAME > /dev/null 2>&1; then
    log "✅ Database restored successfully"

    # Очищаем временный файл
    if [[ $BACKUP_FILE == *.gz ]]; then
        rm -f $TEMP_SQL
    fi

    # Запускаем сервисы
    log "▶️  Starting services..."
    docker-compose -f /opt/accounting-bot/docker-compose.yml start bot api

    log "✨ Restore completed successfully!"
else
    error "Failed to restore database"

    # Очищаем временный файл
    if [[ $BACKUP_FILE == *.gz ]]; then
        rm -f $TEMP_SQL
    fi

    exit 1
fi
