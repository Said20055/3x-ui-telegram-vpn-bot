# tgbot/handlers/user/profile.py (ФИНАЛЬНАЯ УПРОЩЕННАЯ ВЕРСИЯ)

from aiogram import Router, F, types, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from datetime import datetime

from loader import logger
from xui.init_client import XUIClient
from tgbot.keyboards.inline import profile_keyboard
from tgbot.services import qr_generator
from tgbot.services.utils import format_traffic, get_xui_user_info, get_user_attribute

profile_router = Router()


# --- ОСНОВНАЯ ФУНКЦИЯ ДЛЯ ПОКАЗА ПРОФИЛЯ ---
async def show_profile_logic(event: Message | CallbackQuery, xui: XUIClient, bot: Bot):
    """
    Универсальная логика для отображения профиля пользователя.
    Получает все данные и генерирует сообщение с QR-кодом и ссылкой.
    """
    user_id = event.from_user.id
    
    # 1. Получаем данные из БД и панели 3x-ui
    db_user, xui_user = await get_xui_user_info(event, xui)
    
    # Если get_xui_user_info вернула None, она уже отправила сообщение пользователю.
    if not xui_user or not db_user or not db_user.xui_username:
        return

    # 2. Форматируем данные о подписке (статус, дата, трафик)
    is_enabled = get_user_attribute(xui_user, 'enable', False)
    expiry_time_ms = get_user_attribute(xui_user, 'expiryTime', 0)
    is_active = is_enabled and expiry_time_ms > (datetime.now().timestamp() * 1000)
    status_str = "Активен ✅" if is_active else "Неактивен ❌"
    
    expire_date_str = datetime.fromtimestamp(expiry_time_ms / 1000).strftime('%d.%m.%Y %H:%M') if expiry_time_ms else "Никогда"

    up = get_user_attribute(xui_user, 'up', 0)
    down = get_user_attribute(xui_user, 'down', 0)
    used_traffic = up + down
    data_limit = get_user_attribute(xui_user, 'totalGB', 0)
    
    used_traffic_str = format_traffic(used_traffic)
    data_limit_str = "Безлимит" if data_limit == 0 else format_traffic(data_limit)

    # 3. --- ГЛАВНОЕ ИЗМЕНЕНИЕ: ПОЛУЧАЕМ ССЫЛКУ ОДНИМ МЕТОДОМ ---
    # Вся сложная логика сборки теперь внутри клиента
    full_sub_url = await xui.get_user_config_link(db_user.xui_username)
    
    if not full_sub_url:
        full_sub_url = "Не удалось сгенерировать ссылку. Обратитесь в поддержку."

    # 4. Собираем итоговый текст
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🔑 <b>Статус:</b> <code>{status_str}</code>\n"
        f"🗓 <b>Подписка активна до:</b> <code>{expire_date_str}</code>\n\n"
        f"📊 <b>Трафик:</b>\n"
        f"Использовано: <code>{used_traffic_str}</code>\n"
        f"Лимит: <code>{data_limit_str}</code>"
        # Ссылку добавим в caption к фото, чтобы не дублировать
    )

    # 5. Отправляем ответ с QR-кодом
    try:
        qr_code_stream = qr_generator.create_qr_code(full_sub_url)
        qr_photo = types.BufferedInputFile(qr_code_stream.getvalue(), filename="qr.png")

        # Добавляем ссылку в подпись к фото
        caption_with_link = profile_text + f"\n\n🔗 <b>Ваш ключ-конфиг (нажмите, чтобы скопировать):</b>\n<code>{full_sub_url}</code>"

        if isinstance(event, types.CallbackQuery):
            try:
                # Пытаемся отредактировать медиа, если это возможно
                await event.message.edit_media(
                    media=types.InputMediaPhoto(media=qr_photo, caption=caption_with_link),
                    reply_markup=profile_keyboard(full_sub_url)
                )
                return # Если получилось, выходим
            except TelegramBadRequest:
                # Если не вышло (например, прошлое сообщение было текстовым), удаляем и шлем новое
                try:
                    await event.message.delete()
                except TelegramBadRequest:
                    pass
        
        # Отправляем новое сообщение с фото
        await bot.send_photo(
            chat_id=user_id,
            photo=qr_photo,
            caption=caption_with_link,
            reply_markup=profile_keyboard(full_sub_url)
        )

    except Exception as e:
        logger.error(f"Error sending profile with QR: {e}", exc_info=True)
        # Если что-то пошло не так с QR, отправляем просто текст
        text_with_link = profile_text + f"\n\n🔗 <b>Ваш ключ-конфиг (нажмите, чтобы скопировать):</b>\n<code>{full_sub_url}</code>"
        if isinstance(event, types.CallbackQuery):
             await event.message.edit_text(text_with_link, reply_markup=profile_keyboard(full_sub_url))
        else:
             await event.answer(text_with_link, reply_markup=profile_keyboard(full_sub_url))


# --- ХЕНДЛЕРЫ ДЛЯ КОМАНДЫ И КНОПКИ ---
@profile_router.message(Command("profile"))
async def profile_command_handler(message: Message, xui: XUIClient, bot: Bot):
    await show_profile_logic(message, xui, bot)

@profile_router.callback_query(F.data == "my_profile")
async def my_profile_callback_handler(call: CallbackQuery, xui: XUIClient, bot: Bot):
    await call.answer("Обновляю информацию...")
    await show_profile_logic(call, xui, bot)