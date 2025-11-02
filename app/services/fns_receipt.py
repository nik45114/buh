"""
Сервис работы с чеками ФНС через QR-код
Декодирование QR → запрос к API ФНС → получение данных чека
"""

import aiohttp
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class FNSReceiptService:
    """
    Работа с чеками ФНС

    API документация: https://проверить-чек.рф/dev
    """

    def __init__(self):
        # URL API ФНС для проверки чеков
        self.api_url = "https://проверка-чека.рус/api/v1/check"
        # Альтернативный API
        self.alt_api_url = "https://receipt.taxcom.ru/v01/extract"

    def parse_qr_code(self, qr_data: str) -> Optional[Dict]:
        """
        Парсинг QR-кода с чека

        Формат QR-кода:
        t=20240115T1530&s=1500.00&fn=9999078900004792&i=12345&fp=3522207165&n=1

        Параметры:
        - t: дата и время (YYYYMMDDTHHmm)
        - s: сумма
        - fn: номер ФН (фискальный накопитель)
        - i: номер ФД (фискальный документ)
        - fp: ФП (фискальный признак)
        - n: тип операции (1-приход, 2-возврат прихода, 3-расход, 4-возврат расхода)

        Returns:
            Dict с параметрами чека или None
        """
        try:
            params = {}

            # Парсинг строки QR
            for pair in qr_data.split('&'):
                key, value = pair.split('=')
                params[key] = value

            # Обязательные параметры
            required = ['t', 's', 'fn', 'i', 'fp']
            if not all(k in params for k in required):
                logger.error(f"Missing required QR parameters: {params}")
                return None

            # Парсинг даты
            date_str = params['t']
            purchase_date = datetime.strptime(date_str, "%Y%m%dT%H%M")

            # Парсинг суммы
            total_amount = Decimal(params['s'])

            # Тип операции
            operation_type_code = int(params.get('n', 1))
            operation_types = {
                1: "income",
                2: "income_return",
                3: "expense",
                4: "expense_return"
            }
            operation_type = operation_types.get(operation_type_code, "income")

            return {
                "purchase_date": purchase_date,
                "total_amount": total_amount,
                "fiscal_storage": params['fn'],
                "fiscal_document": params['i'],
                "fiscal_sign": params['fp'],
                "operation_type": operation_type,
                "qr_raw": qr_data
            }

        except Exception as e:
            logger.error(f"Error parsing QR code: {e}")
            return None

    async def get_receipt_details(
        self,
        fiscal_sign: str,
        fiscal_document: str,
        fiscal_storage: str,
        purchase_date: datetime
    ) -> Optional[Dict]:
        """
        Получить детали чека от ФНС

        Использует публичный API для проверки чеков

        Returns:
            Полные данные чека или None
        """
        try:
            # Формат даты для API
            date_str = purchase_date.strftime("%Y%m%dT%H%M")

            # Параметры запроса
            params = {
                "fn": fiscal_storage,
                "i": fiscal_document,
                "fp": fiscal_sign,
                "t": date_str
            }

            async with aiohttp.ClientSession() as session:
                # Пробуем основной API
                async with session.get(self.api_url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return self._parse_fns_response(data)

                # Если не сработало, пробуем альтернативный API
                async with session.post(
                    self.alt_api_url,
                    json=params,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return self._parse_fns_response(data)

            logger.warning("Could not fetch receipt details from FNS API")
            return None

        except Exception as e:
            logger.error(f"Error fetching receipt from FNS: {e}")
            return None

    def _parse_fns_response(self, data: Dict) -> Dict:
        """
        Парсинг ответа от API ФНС

        Извлекает нужные поля
        """
        try:
            # Структура может отличаться в зависимости от API
            # Адаптируем под разные форматы

            receipt_data = data.get("document", {}).get("receipt", data.get("ticket", data))

            return {
                "seller_name": receipt_data.get("user", receipt_data.get("retailPlace")),
                "seller_inn": receipt_data.get("userInn"),
                "seller_address": receipt_data.get("retailPlaceAddress"),
                "cashier": receipt_data.get("operator"),
                "shift_number": receipt_data.get("shiftNumber"),
                "total_amount": Decimal(str(receipt_data.get("totalSum", 0))) / 100,  # копейки → рубли
                "vat_amount": Decimal(str(receipt_data.get("nds18", 0))) / 100,
                "payment_type": "cash" if receipt_data.get("cashTotalSum", 0) > 0 else "card",
                "items": self._parse_items(receipt_data.get("items", [])),
                "taxation_type": receipt_data.get("taxationType"),
                "raw_data": data
            }

        except Exception as e:
            logger.error(f"Error parsing FNS response: {e}")
            return {"raw_data": data}

    def _parse_items(self, items: list) -> list:
        """
        Парсинг товаров из чека

        Returns:
            [{"name": "Товар", "quantity": 1, "price": 100, "sum": 100}, ...]
        """
        parsed_items = []

        for item in items:
            try:
                parsed_items.append({
                    "name": item.get("name"),
                    "quantity": item.get("quantity", 1),
                    "price": Decimal(str(item.get("price", 0))) / 100,
                    "sum": Decimal(str(item.get("sum", 0))) / 100
                })
            except Exception as e:
                logger.warning(f"Error parsing item: {e}")
                continue

        return parsed_items

    async def verify_and_save_receipt(self, qr_data: str) -> Optional[Dict]:
        """
        Полный цикл: парсинг QR → запрос к ФНС → валидация

        Returns:
            Полные данные чека готовые для сохранения в БД
        """
        # 1. Парсим QR
        qr_params = self.parse_qr_code(qr_data)
        if not qr_params:
            return None

        # 2. Запрашиваем детали у ФНС
        details = await self.get_receipt_details(
            fiscal_sign=qr_params["fiscal_sign"],
            fiscal_document=qr_params["fiscal_document"],
            fiscal_storage=qr_params["fiscal_storage"],
            purchase_date=qr_params["purchase_date"]
        )

        # 3. Объединяем данные
        if details:
            qr_params.update(details)

        # 4. Формируем URL чека на сайте ФНС
        qr_params["fns_url"] = self._build_fns_url(qr_params)

        return qr_params

    def _build_fns_url(self, params: Dict) -> str:
        """
        Создать URL для просмотра чека на сайте ФНС

        https://lknpd.nalog.ru/api/v1/receipt/{userId}/{receiptId}/print
        """
        # Упрощенный вариант
        fn = params.get("fiscal_storage", "")
        fd = params.get("fiscal_document", "")
        fp = params.get("fiscal_sign", "")

        return f"https://check.ofd.ru/rec/{fp}/{fd}/{fn}"


# Singleton instance
fns_receipt_service = FNSReceiptService()
