# Accounting Bot

Telegram бот для управления бухгалтерией с API и интеграцией AI.

## Возможности

- Управление клиентами и проектами через Telegram
- REST API для интеграции
- Автоматическая генерация документов
- Бэкапы базы данных
- AI-ассистент для работы с данными

## Быстрый старт

### Локальная разработка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/nik45114/buh.git
cd buh
```

2. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
# Отредактируйте .env и укажите свои параметры
```

3. Запустите с помощью Docker Compose:
```bash
docker-compose up -d
```

### Production деплой

Для production используйте предсобранные образы из GitHub Container Registry:

1. Подготовьте `.env` файл с настройками

2. Запустите production версию:
```bash
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

3. Обновление до последней версии:
```bash
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

## Автоматическая сборка

При каждом push в ветку `main`:
- Автоматически собирается Docker-образ
- Публикуется в GitHub Container Registry
- Доступен по адресу: `ghcr.io/nik45114/buh:latest`

### Ручной запуск сборки

Перейдите в GitHub Actions → "Build and Deploy" → "Run workflow"

## Структура проекта

```
.
├── app/                    # Исходный код приложения
│   ├── main.py            # Точка входа для бота
│   ├── api/               # REST API
│   ├── bot/               # Telegram бот
│   ├── database/          # Модели и работа с БД
│   └── services/          # Бизнес-логика
├── migrations/            # Миграции базы данных
├── templates/             # Шаблоны документов
├── scripts/               # Утилитные скрипты
├── tests/                 # Тесты
├── docker-compose.yml     # Локальная разработка
├── docker-compose.prod.yml # Production деплой
└── Dockerfile            # Образ приложения
```

## Разработка

### Требования

- Python 3.11+
- PostgreSQL 15+
- Docker и Docker Compose (опционально)

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Миграции БД

```bash
alembic upgrade head
```

## Бэкапы

Бэкапы базы данных сохраняются в директории `./backups`

## Документы

Сгенерированные документы сохраняются в `./documents`

## API

API доступен по адресу `http://localhost:${API_PORT}` (по умолчанию 8000)

Документация Swagger: `http://localhost:${API_PORT}/docs`

## Лицензия

MIT
