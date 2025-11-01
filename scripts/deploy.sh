#!/bin/bash
set -e

# ═══════════════════════════════════════════════════
# Скрипт развертывания на VPS
# ═══════════════════════════════════════════════════

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="/opt/accounting-bot"

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log "🚀 Starting deployment..."

# Проверка наличия Docker
if ! command -v docker &> /dev/null; then
    error "Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed"
    exit 1
fi

# Переход в директорию проекта
cd $PROJECT_DIR

# Проверка .env файла
if [ ! -f ".env" ]; then
    warning ".env file not found"
    if [ -f ".env.example" ]; then
        info "Creating .env from .env.example"
        cp .env.example .env
        warning "Please edit .env file with your configuration"
        exit 1
    else
        error ".env.example not found"
        exit 1
    fi
fi

# Остановка контейнеров
log "⏸️  Stopping existing containers..."
docker-compose down || true

# Удаление старых образов
log "🗑️  Removing old images..."
docker-compose rm -f || true

# Сборка образов
log "🔨 Building images..."
docker-compose build --no-cache

# Запуск контейнеров
log "▶️  Starting containers..."
docker-compose up -d

# Ожидание запуска PostgreSQL
log "⏳ Waiting for PostgreSQL..."
sleep 10

# Проверка состояния контейнеров
log "🔍 Checking container status..."
docker-compose ps

# Проверка логов
log "📋 Recent logs:"
docker-compose logs --tail=20

# Создание cron задачи для бэкапов
log "⏰ Setting up backup cron job..."
CRON_JOB="0 3 * * * $PROJECT_DIR/scripts/backup.sh >> /var/log/accounting_backup.log 2>&1"

# Проверяем есть ли уже такая задача
if ! crontab -l 2>/dev/null | grep -q "$PROJECT_DIR/scripts/backup.sh"; then
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    log "✅ Backup cron job added (daily at 3 AM)"
else
    info "Backup cron job already exists"
fi

log "✨ Deployment completed!"
echo ""
info "Services:"
info "  Bot: running in container 'accounting_bot'"
info "  API: http://localhost:${API_PORT:-8000}"
info "  Docs: http://localhost:${API_PORT:-8000}/docs"
echo ""
info "Useful commands:"
info "  docker-compose logs -f bot      # View bot logs"
info "  docker-compose logs -f api      # View API logs"
info "  docker-compose restart          # Restart all services"
info "  ./scripts/backup.sh             # Manual backup"
echo ""
log "🎉 Ready to use!"
