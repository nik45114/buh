"""
OCR сервис для распознавания чеков через OpenAI Vision API
"""
from openai import OpenAI
from app.config import settings
from typing import Dict, Optional
import json
import logging
import base64

logger = logging.getLogger(__name__)


async def recognize_receipt(image_bytes: bytes) -> Optional[Dict]:
    """
    Распознавание чека через OpenAI Vision API (GPT-4 Vision)

    Args:
        image_bytes: Байты изображения чека

    Returns:
        Dict с данными чека или None при ошибке
    """
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Кодируем изображение в base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Промпт для GPT-4 Vision
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

        # Запрос к OpenAI GPT-4 Vision
        response = client.chat.completions.create(
            model="gpt-4o",  # gpt-4o поддерживает vision и дешевле
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
        )

        # Парсим ответ
        response_text = response.choices[0].message.content

        # Извлекаем JSON из ответа
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
        logger.error(f"Error parsing JSON from OpenAI response: {e}")
        logger.error(f"Response text: {response_text}")
        return None
    except Exception as e:
        logger.error(f"Error recognizing receipt: {e}")
        return None


async def categorize_expense(description: str, items: list = None) -> str:
    """
    Автоматическая категоризация расхода через OpenAI API

    Args:
        description: Описание расхода
        items: Список товаров/услуг

    Returns:
        Название категории
    """
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

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

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Для простой категоризации достаточно 3.5
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )

        category = response.choices[0].message.content.strip()
        logger.info(f"Expense categorized: {description} -> {category}")
        return category

    except Exception as e:
        logger.error(f"Error categorizing expense: {e}")
        return "Прочие расходы"
