"""
OCR сервис для распознавания чеков через Claude Vision API
"""
import anthropic
from app.config import settings
from typing import Dict, Optional
import json
import logging
import base64

logger = logging.getLogger(__name__)


async def recognize_receipt(image_bytes: bytes) -> Optional[Dict]:
    """
    Распознавание чека через Claude Vision API

    Args:
        image_bytes: Байты изображения чека

    Returns:
        Dict с данными чека или None при ошибке
    """
    try:
        client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

        # Кодируем изображение в base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Промпт для Claude
        prompt = """
Распознай чек и верни ТОЛЬКО JSON в формате:
{
  "date": "YYYY-MM-DD",
  "amount": 5000.00,
  "seller": "Название продавца",
  "seller_inn": "ИНН если есть",
  "items": ["Товар 1", "Товар 2"],
  "category": "категория",
  "payment_method": "cash/cashless/card"
}

Категории для УСН "доходы-расходы":
- "Материальные расходы" - сырье, материалы, комплектующие
- "Товары для перепродажи" - товары для перепродажи
- "Аренда помещений" - аренда помещений, оборудования
- "Услуги связи и интернет" - интернет, телефон, хостинг
- "Транспортные расходы" - ГСМ, такси, доставка
- "Канцелярские товары" - бумага, ручки, папки
- "Программное обеспечение" - программы, подписки, лицензии
- "Ремонт и обслуживание" - ремонт и обслуживание
- "Реклама и маркетинг" - реклама, продвижение
- "Оплата труда" - зарплата сотрудников
- "Банковские услуги" - комиссии банка
- "Налоги и сборы" - налоги и сборы
- "Коммунальные услуги" - электричество, вода, отопление
- "Прочие расходы" - другие расходы

Определи наиболее подходящую категорию на основе содержимого чека.
Не добавляй никаких комментариев, только JSON.
"""

        # Запрос к Claude
        message = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )

        # Парсим ответ
        response_text = message.content[0].text

        # Извлекаем JSON из ответа
        # Claude может вернуть JSON в markdown блоке
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()

        receipt_data = json.loads(json_str)

        logger.info(f"Receipt recognized: {receipt_data.get('seller')}, amount: {receipt_data.get('amount')}")
        return receipt_data

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from Claude response: {e}")
        logger.error(f"Response text: {response_text}")
        return None
    except Exception as e:
        logger.error(f"Error recognizing receipt: {e}")
        return None


async def categorize_expense(description: str, items: list = None) -> str:
    """
    Автоматическая категоризация расхода через Claude API

    Args:
        description: Описание расхода
        items: Список товаров/услуг

    Returns:
        Название категории
    """
    try:
        client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

        items_text = ", ".join(items) if items else "нет данных"

        prompt = f"""
Определи категорию расхода для УСН "доходы-расходы".

Описание: {description}
Товары/услуги: {items_text}

Верни ТОЛЬКО название одной из категорий:
- Материальные расходы
- Товары для перепродажи
- Аренда помещений
- Услуги связи и интернет
- Транспортные расходы
- Канцелярские товары
- Программное обеспечение
- Ремонт и обслуживание
- Реклама и маркетинг
- Оплата труда
- Банковские услуги
- Налоги и сборы
- Коммунальные услуги
- Прочие расходы

Верни только название категории, без пояснений.
"""

        message = client.messages.create(
            model="claude-3-haiku-20240307",  # Используем быструю модель
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )

        category = message.content[0].text.strip()
        logger.info(f"Expense categorized: {description} -> {category}")
        return category

    except Exception as e:
        logger.error(f"Error categorizing expense: {e}")
        return "Прочие расходы"
