"""
Фильтры для Telegram бота
"""
from aiogram.filters import Filter
from aiogram.types import Message
from app.config import settings


class IsOwner(Filter):
    """Проверка что пользователь - владелец"""

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id == settings.OWNER_TELEGRAM_ID


class IsAdmin(Filter):
    """Проверка что пользователь - админ или владелец"""

    async def __call__(self, message: Message) -> bool:
        return (
            message.from_user.id == settings.OWNER_TELEGRAM_ID or
            message.from_user.id in settings.admin_ids
        )
