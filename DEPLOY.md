# 📦 Инструкция по развертыванию Accounting Bot

## Требования к серверу

- **OS**: Ubuntu 20.04 / 22.04 LTS или Debian 11+
- **RAM**: минимум 2GB (рекомендуется 4GB)
- **Диск**: минимум 20GB SSD
- **Docker**: версия 20.10+
- **Docker Compose**: версия 2.0+

## Шаг 1: Подготовка сервера

### Обновление системы

```bash
sudo apt update && sudo apt upgrade -y
```

### Установка Docker

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Перелогиниться для применения изменений
exit
# Зайти снова через SSH
```

### Установка Docker Compose

```bash
sudo apt install docker-compose-plugin -y
```

## Шаг 2: Клонирование проекта

```bash
cd /opt
sudo mkdir accounting-bot
sudo chown $USER:$USER accounting-bot
cd accounting-bot

# Скопировать файлы проекта на сервер
# Можно использовать git clone, scp, rsync и т.д.
```

## Шаг 3: Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

### Обязательные переменные:

```env
# Telegram Bot
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
OWNER_TELEGRAM_ID=123456789
ADMIN_TELEGRAM_IDS=[987654321,111222333]
ADMIN_CHAT_ID=-1001234567890

# Claude API
CLAUDE_API_KEY=sk-ant-api03-xxxxxxxxxxxxx
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=accounting
DB_USER=accounting
DB_PASSWORD=STRONG_PASSWORD_HERE_123

# API
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=RANDOM_API_KEY_123456789

# Company
COMPANY_NAME=ООО "Лепта"
COMPANY_INN=6829164121
TAX_SYSTEM=usn_income_expense
TAX_RATE=0.15
```

### Как получить параметры:

#### BOT_TOKEN
1. Откройте Telegram
2. Найдите @BotFather
3. Отправьте `/newbot`
4. Следуйте инструкциям
5. Скопируйте полученный токен

#### OWNER_TELEGRAM_ID
1. Найдите в Telegram бота @userinfobot
2. Отправьте ему `/start`
3. Он вернет ваш ID

#### ADMIN_CHAT_ID
1. Создайте группу в Telegram
2. Добавьте туда бота @userinfobot
3. Отправьте любое сообщение
4. Бот покажет ID группы (начинается с минуса)

#### CLAUDE_API_KEY
1. Зарегистрируйтесь на https://console.anthropic.com/
2. Перейдите в раздел API Keys
3. Создайте новый ключ
4. Пополните баланс (минимум $10)

#### Генерация случайных ключей:

```bash
# DB_PASSWORD
openssl rand -base64 32

# API_KEY
openssl rand -hex 32
```

## Шаг 4: Развертывание

```bash
# Сделать скрипты исполняемыми
chmod +x scripts/*.sh

# Запустить развертывание
./scripts/deploy.sh
```

Скрипт автоматически:
- Остановит старые контейнеры (если есть)
- Соберет Docker образы
- Запустит контейнеры
- Настроит автоматические бэкапы

## Шаг 5: Проверка

### Проверить статус контейнеров

```bash
docker-compose ps
```

Должны быть запущены:
- `accounting_postgres` - база данных
- `accounting_bot` - Telegram бот
- `accounting_api` - API сервер

### Проверить логи

```bash
# Логи бота
docker-compose logs -f bot

# Логи API
docker-compose logs -f api

# Логи PostgreSQL
docker-compose logs -f postgres
```

### Проверить API

```bash
# Health check
curl http://localhost:8000/health

# Должен вернуть:
# {"status":"ok","service":"accounting-bot-api"}
```

### Проверить бота

1. Откройте Telegram
2. Найдите вашего бота
3. Отправьте `/start`
4. Должно появиться главное меню

## Шаг 6: Настройка firewall (опционально)

Если API нужен только локально:

```bash
# Разрешить только локальные подключения к API
sudo ufw allow 22/tcp
sudo ufw allow from 127.0.0.1 to any port 8000
sudo ufw enable
```

Если API нужен извне (для Bot_Claude):

```bash
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp
sudo ufw enable
```

## Шаг 7: Настройка автозапуска (опционально)

Docker Compose автоматически перезапустит контейнеры после перезагрузки сервера.

Если нужно убедиться:

```bash
# Проверить политику перезапуска
docker inspect accounting_bot | grep -A 5 RestartPolicy
```

Должно быть:
```json
"RestartPolicy": {
    "Name": "always"
}
```

## Шаг 8: Тестирование интеграции с Bot_Claude

### На сервере Bot_Claude:

```bash
# Отправить тестовый отчет о смене
curl -X POST http://your-accounting-server:8000/api/shift-report \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2024-01-15",
    "shift": "evening",
    "cash_fact": 15000.00,
    "cashless_fact": 8000.00,
    "qr_payments": 3500.00
  }'
```

Должен вернуть:
```json
{
  "status": "success",
  "message": "Shift report processed successfully"
}
```

## Шаг 9: Настройка мониторинга

### Создание скрипта проверки здоровья

```bash
nano /opt/accounting-bot/scripts/health_check.sh
```

```bash
#!/bin/bash
# Проверка работоспособности

# Проверка контейнеров
if ! docker-compose ps | grep -q "Up"; then
    echo "CRITICAL: Some containers are down"
    exit 2
fi

# Проверка API
if ! curl -s http://localhost:8000/health | grep -q "ok"; then
    echo "CRITICAL: API not responding"
    exit 2
fi

echo "OK: All services running"
exit 0
```

```bash
chmod +x /opt/accounting-bot/scripts/health_check.sh
```

### Добавление в cron для мониторинга

```bash
crontab -e
```

Добавить:
```bash
# Health check каждые 5 минут
*/5 * * * * /opt/accounting-bot/scripts/health_check.sh >> /var/log/accounting_health.log 2>&1
```

## Обслуживание

### Просмотр логов

```bash
# Последние 100 строк
docker-compose logs --tail=100 bot

# Следить за логами в реальном времени
docker-compose logs -f bot api
```

### Перезапуск сервисов

```bash
# Перезапустить все
docker-compose restart

# Перезапустить только бота
docker-compose restart bot
```

### Обновление

```bash
cd /opt/accounting-bot
git pull  # или скопировать новые файлы
./scripts/deploy.sh
```

### Бэкапы

```bash
# Ручной бэкап
./scripts/backup.sh

# Посмотреть бэкапы
ls -lh backups/daily/

# Восстановление
./scripts/restore.sh backups/daily/backup_20240115_030000.sql.gz
```

## Решение проблем

### Проблема: Контейнеры не запускаются

```bash
# Проверить логи
docker-compose logs

# Проверить .env
cat .env | grep -v "^#"

# Пересоздать контейнеры
docker-compose down -v
./scripts/deploy.sh
```

### Проблема: PostgreSQL не запускается

```bash
# Проверить логи PostgreSQL
docker-compose logs postgres

# Проверить права на папку
ls -la backups/

# Пересоздать volume
docker-compose down -v
docker volume rm accounting-bot_postgres_data
./scripts/deploy.sh
```

### Проблема: Бот не отвечает

```bash
# Проверить токен
echo $BOT_TOKEN

# Проверить логи
docker-compose logs bot

# Перезапустить
docker-compose restart bot
```

### Проблема: API не доступен

```bash
# Проверить порт
netstat -tlnp | grep 8000

# Проверить firewall
sudo ufw status

# Перезапустить
docker-compose restart api
```

## Безопасность

### Рекомендации:

1. ✅ Использовать сильные пароли для БД
2. ✅ Не публиковать .env файл
3. ✅ Настроить firewall
4. ✅ Регулярно обновлять систему
5. ✅ Делать регулярные бэкапы
6. ✅ Ограничить доступ к API по IP (если возможно)
7. ✅ Использовать HTTPS для API (через nginx reverse proxy)

### Настройка HTTPS (опционально)

```bash
# Установить nginx
sudo apt install nginx certbot python3-certbot-nginx -y

# Создать конфигурацию
sudo nano /etc/nginx/sites-available/accounting-api
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Активировать конфигурацию
sudo ln -s /etc/nginx/sites-available/accounting-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Получить SSL сертификат
sudo certbot --nginx -d your-domain.com
```

---

✅ **Развертывание завершено!**

Теперь ваш Accounting Bot готов к использованию.
