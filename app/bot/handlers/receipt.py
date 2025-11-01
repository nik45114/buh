"""
Обработка фото чеков
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.services.ocr_service import recognize_receipt
from app.database.db import async_session_maker
from app.database import crud
from app.bot.keyboards import get_receipt_confirmation_keyboard
from datetime import datetime
from decimal import Decimal
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext):
    """Обработка фото чеков"""
    await message.answer("🔍 Распознаю чек...")

    try:
        # Скачиваем фото (берем самое большое разрешение)
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        photo_bytes = await message.bot.download_file(file.file_path)

        # Читаем байты
        photo_data = photo_bytes.read()

        # OCR через Claude Vision
        receipt_data = await recognize_receipt(photo_data)

        if not receipt_data:
            await message.answer(
                "❌ Не удалось распознать чек. Попробуйте:\n"
                "• Сфотографировать чек четче\n"
                "• Добавить данные вручную командой /add"
            )
            return

        # Сохраняем данные в состояние
        await state.update_data(
            receipt_data=receipt_data,
            photo_file_id=photo.file_id,
            user_id=message.from_user.id
        )

        # Показываем результат
        text = (
            f"✅ <b>Чек распознан</b>\n\n"
            f"📅 Дата: {receipt_data.get('date', 'не указана')}\n"
            f"💰 Сумма: <b>{receipt_data.get('amount', 0):,.2f} ₽</b>\n"
            f"🏪 Продавец: {receipt_data.get('seller', 'не указан')}\n"
        )

        if receipt_data.get('seller_inn'):
            text += f"🔢 ИНН: {receipt_data['seller_inn']}\n"

        if receipt_data.get('items'):
            items_list = receipt_data['items'][:5]  # Показываем только первые 5
            text += f"📦 Товары: {', '.join(items_list)}\n"
            if len(receipt_data['items']) > 5:
                text += f"   ... и еще {len(receipt_data['items']) - 5}\n"

        text += f"📂 Категория: {receipt_data.get('category', 'не определена')}\n"
        text += f"💳 Оплата: {receipt_data.get('payment_method', 'не указана')}\n\n"
        text += "Подтвердить добавление?"

        # Клавиатура подтверждения
        keyboard = get_receipt_confirmation_keyboard(receipt_data)

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error processing receipt photo: {e}")
        await message.answer(
            "❌ Ошибка при обработке фото. Попробуйте еще раз или добавьте данные вручную."
        )


@router.callback_query(F.data.startswith("confirm_receipt:"))
async def callback_confirm_receipt(callback: CallbackQuery, state: FSMContext):
    """Подтверждение добавления чека"""
    data = await state.get_data()
    receipt_data = data.get('receipt_data')

    if not receipt_data:
        await callback.answer("❌ Данные чека не найдены", show_alert=True)
        return

    async with async_session_maker() as session:
        # Получаем пользователя
        user = await crud.get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name
        )

        # Получаем категорию по имени
        category = await crud.get_category_by_name(session, receipt_data.get('category', 'Прочие расходы'))

        # Создаем транзакцию
        transaction_data = {
            'date': datetime.strptime(receipt_data.get('date'), '%Y-%m-%d').date() if receipt_data.get('date') else datetime.now().date(),
            'type': 'expense',
            'amount': Decimal(str(receipt_data.get('amount', 0))),
            'category_id': category.id if category else None,
            'counterparty': receipt_data.get('seller'),
            'counterparty_inn': receipt_data.get('seller_inn'),
            'description': ', '.join(receipt_data.get('items', [])) if receipt_data.get('items') else None,
            'payment_method': receipt_data.get('payment_method', 'cash'),
            'source': 'photo',
            'is_confirmed': False,  # Требует подтверждения администратора
            'created_by': user.id
        }

        transaction = await crud.create_transaction(session, transaction_data)

        # Сохраняем документ (фото чека)
        document_data = {
            'transaction_id': transaction.id,
            'file_type': 'receipt',
            'telegram_file_id': data.get('photo_file_id'),
            'ocr_data': receipt_data,
            'uploaded_by': user.id
        }

        await crud.create_document(session, document_data)

    await callback.message.edit_text(
        f"✅ <b>Расход добавлен</b>\n\n"
        f"💰 Сумма: {receipt_data.get('amount', 0):,.2f} ₽\n"
        f"📂 Категория: {receipt_data.get('category')}\n"
        f"🏪 Продавец: {receipt_data.get('seller')}\n\n"
        f"⏳ Ожидает подтверждения администратора",
        parse_mode="HTML"
    )

    await state.clear()
    await callback.answer("✅ Расход добавлен")


@router.callback_query(F.data == "edit_receipt")
async def callback_edit_receipt(callback: CallbackQuery):
    """Редактирование чека"""
    await callback.message.edit_text(
        "✏️ Редактирование чека пока не реализовано.\n"
        "Используйте /add для ручного ввода данных.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_receipt")
async def callback_cancel_receipt(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления чека"""
    await state.clear()
    await callback.message.edit_text("❌ Добавление чека отменено")
    await callback.answer()
