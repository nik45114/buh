#!/bin/bash
set -e

# ═══════════════════════════════════════════════════
# Автоматический бэкап базы данных PostgreSQL
# ═══════════════════════════════════════════════════

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Загрузка переменных из .env
ENV_FILE="/opt/accounting-bot/.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' $ENV_FILE | xargs)
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Конфигурация
BACKUP_DIR="/opt/accounting-bot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)
DAY_OF_MONTH=$(date +%d)
RETENTION_DAILY=30
RETENTION_WEEKLY=90
RETENTION_MONTHLY=365

# Создаем директории
mkdir -p $BACKUP_DIR/daily
mkdir -p $BACKUP_DIR/weekly
mkdir -p $BACKUP_DIR/monthly

# Функция логирования
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Функция отправки в Telegram
send_telegram() {
    local message="$1"
    if [ -n "$BOT_TOKEN" ] && [ -n "$ADMIN_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
            -d chat_id="${ADMIN_CHAT_ID}" \
            -d text="${message}" \
            -d parse_mode="HTML" > /dev/null 2>&1
    fi
}

log "🔄 Starting database backup..."

# Проверяем доступность PostgreSQL
if ! docker exec accounting_postgres pg_isready -U $DB_USER > /dev/null 2>&1; then
    error "PostgreSQL is not available"
    send_telegram "❌ <b>Backup Failed</b>%0APostgreSQL не доступен"
    exit 1
fi

# Создаем дамп БД
BACKUP_FILE="$BACKUP_DIR/daily/backup_${DATE}.sql"

if docker exec accounting_postgres pg_dump \
    -U $DB_USER \
    -d $DB_NAME \
    -F p \
    --no-owner \
    --no-acl \
    > $BACKUP_FILE 2>/dev/null; then

    # Проверяем размер
    BACKUP_SIZE=$(du -h $BACKUP_FILE | cut -f1)
    log "✅ Backup created: $BACKUP_SIZE"

    # Сжимаем
    gzip $BACKUP_FILE
    COMPRESSED_SIZE=$(du -h ${BACKUP_FILE}.gz | cut -f1)
    log "📦 Compressed: $COMPRESSED_SIZE"

    # Еженедельный бэкап (воскресенье)
    if [ $DAY_OF_WEEK -eq 7 ]; then
        cp ${BACKUP_FILE}.gz $BACKUP_DIR/weekly/
        log "📅 Weekly backup created"
    fi

    # Ежемесячный бэкап (1 число)
    if [ $DAY_OF_MONTH -eq 01 ]; then
        cp ${BACKUP_FILE}.gz $BACKUP_DIR/monthly/
        log "📅 Monthly backup created"
    fi

    # Очистка старых бэкапов
    log "🗑️  Cleaning old backups..."
    find $BACKUP_DIR/daily -name "backup_*.sql.gz" -mtime +$RETENTION_DAILY -delete
    find $BACKUP_DIR/weekly -name "backup_*.sql.gz" -mtime +$RETENTION_WEEKLY -delete
    find $BACKUP_DIR/monthly -name "backup_*.sql.gz" -mtime +$RETENTION_MONTHLY -delete

    # Проверка целостности
    log "🔍 Verifying backup integrity..."
    if gzip -t ${BACKUP_FILE}.gz 2>/dev/null; then
        log "✅ Backup integrity OK"
        STATUS="✅ Бэкап успешно создан"
        MESSAGE="<b>💾 Backup Success</b>%0A%0A"
        MESSAGE+="📅 Дата: $(date '+%d.%m.%Y %H:%M')%0A"
        MESSAGE+="📦 Размер: $COMPRESSED_SIZE%0A"
        MESSAGE+="🗂️  Файл: backup_${DATE}.sql.gz"
    else
        error "Backup verification failed!"
        STATUS="❌ Ошибка бэкапа"
        MESSAGE="<b>⚠️  Backup Failed</b>%0A%0A"
        MESSAGE+="Проверка целостности не прошла"
    fi
else
    error "Failed to create backup"
    STATUS="❌ Ошибка бэкапа"
    MESSAGE="<b>⚠️  Backup Failed</b>%0A%0A"
    MESSAGE+="Не удалось создать дамп БД"
fi

# Отправляем уведомление
send_telegram "$MESSAGE"

log "✨ Backup process completed!"
