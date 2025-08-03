# tgbot/handlers/user/profile.py

from aiogram import Router, F, types, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest
from aiohttp.client_exceptions import ClientConnectionError
from aiogram.filters import Command
from datetime import datetime

from loader import logger
from marzban.init_client import MarzClientCache
from tgbot.keyboards.inline import profile_keyboard, back_to_main_menu_keyboard
from tgbot.services import qr_generator
from tgbot.services.utils import format_traffic, get_marzban_user_info, get_user_attribute
from urllib.parse import quote_plus

profile_router = Router()


# --- 1. Создаем ОБЩУЮ функцию для показа профиля ---
async def show_profile_logic(event: Message | CallbackQuery, marzban: MarzClientCache, bot: Bot):
    """
    Универсальная логика для отображения профиля пользователя.
    Адаптирована для вызова из webhook_handler.
    """
    
    # Получаем ID пользователя и объект бота из события
    user_id = event.from_user.id

    
    # Получаем информацию о пользователе
    db_user, marzban_user = await get_marzban_user_info(event, marzban)
    if not marzban_user:
        return

    # --- Форматирование данных (ваш код) ---
    status = get_user_attribute(marzban_user, 'status', 'unknown')
    expire_ts = get_user_attribute(marzban_user, 'expire')
    expire_date = datetime.fromtimestamp(expire_ts).strftime('%d.%m.%Y %H:%M') if expire_ts else "Никогда"

    used_traffic = get_user_attribute(marzban_user, 'used_traffic', 0)
    data_limit = get_user_attribute(marzban_user, 'data_limit')
    used_traffic_str = format_traffic(used_traffic)
    data_limit_str = "Безлимит" if data_limit == 0 or data_limit is None else format_traffic(data_limit)

    sub_url = get_user_attribute(marzban_user, 'subscription_url', '')
    full_sub_url = f"https://{marzban._config.webhook.domain}:8443{sub_url}" if sub_url else ""

    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🔑 <b>Статус:</b> <code>{status}</code>\n"
        f"🗓 <b>Подписка активна до:</b> <code>{expire_date}</code>\n\n"
        f"📊 <b>Трафик:</b>\n"
        f"Использовано: <code>{used_traffic_str}</code>\n"
        f"Лимит: <code>{data_limit_str}</code>\n\n"
        f"🔗 <b>Ссылка для подписки (нажмите, чтобы скопировать):</b>\n<code>{full_sub_url}</code>"
    )

    # --- Отправка ответа с QR-кодом ---
    try:
        qr_code_stream = qr_generator.create_qr_code(full_sub_url)
        qr_photo = types.BufferedInputFile(qr_code_stream.getvalue(), filename="qr.png")

        # --- ИСПРАВЛЕННАЯ ЛОГИКА ОТПРАВКИ ---
        
        # Если это было нажатие на кнопку, пытаемся удалить старое сообщение
        if isinstance(event, types.CallbackQuery):
            try:
                await event.message.delete()
            except TelegramBadRequest:
                pass # Игнорируем, если не получилось

        # Отправляем новое сообщение с фото напрямую через объект bot
        await bot.send_photo(
            chat_id=user_id,
            photo=qr_photo,
            caption=profile_text,
            reply_markup=profile_keyboard(full_sub_url)
        )

    except Exception as e:
        logger.error(f"Error sending profile with QR: {e}", exc_info=True)
        # Если что-то пошло не так, отправляем просто текст
        
        # --- ИСПРАВЛЕННАЯ ЛОГИКА ОТПРАВКИ ---
        await bot.send_message(
            chat_id=user_id,
            text=profile_text,
            reply_markup=profile_keyboard(full_sub_url)
        )


# --- 2. Хендлеры для команды и кнопки ---
@profile_router.message(Command("profile"))
async def profile_command_handler(message: Message, marzban: MarzClientCache, bot: Bot):
    await show_profile_logic(message, marzban, bot)

@profile_router.callback_query(F.data == "my_profile")
async def my_profile_callback_handler(call: CallbackQuery, marzban: MarzClientCache, bot: Bot):
    await call.answer("Загружаю информацию...")
    await show_profile_logic(call, marzban, bot)


# --- Хендлер для "Мои ключи" (остается почти без изменений) ---
@profile_router.callback_query(F.data == "my_keys")
async def my_keys_handler(call: CallbackQuery, marzban: MarzClientCache):
    """Показывает пользователю его ключи для подключения."""
    await call.answer()
    
    # Используем ту же самую сервисную функцию
    db_user, marzban_user = await get_marzban_user_info(call, marzban)
    if not marzban_user:
        return

    links = get_user_attribute(marzban_user, 'links', [])

    if not links:
        # --- ИСПРАВЛЕННАЯ ЛОГИКА ОТПРАВКИ ---
        text = "К сожалению, для вашей подписки не найдено ключей. Обратитесь в поддержку."
        reply_markup = back_to_main_menu_keyboard()
        try:
            await call.message.edit_text(text, reply_markup=reply_markup)
        except TelegramBadRequest:
            await call.message.delete()
            await call.message.answer(text, reply_markup=reply_markup)
        return

    formatted_links = [f"<code>{link}</code>" for link in links]
    message_text = (
        "🔑 <b>Вот ваши ключи для подключения:</b>\n\n"
        "<i>Нажмите на ключ, чтобы скопировать его, а затем вставьте в вашем VPN-клиенте.</i>\n\n" +
        "\n\n".join(formatted_links)
    )

    # --- ИСПРАВЛЕННАЯ ЛОГИКА ОТПРАВКИ ---
    reply_markup = back_to_main_menu_keyboard()
    try:
        # Пытаемся изменить текущее сообщение (с фото) на новое текстовое
        await call.message.edit_text(
            text=message_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    except TelegramBadRequest:
        # Если не получилось (потому что это было фото), удаляем старое и шлем новое
        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass # Если не можем удалить - не страшно
        await call.message.answer(
            text=message_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
