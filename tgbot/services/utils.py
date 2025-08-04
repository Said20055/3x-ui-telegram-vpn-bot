# tgbot/services/utils.py

from datetime import datetime
# Убедимся, что импортируем наш новый клиент
from xui.init_client import XUIClient
from database import requests as db
from aiogram import types
from aiogram.exceptions import TelegramBadRequest

from tgbot.keyboards.inline import back_to_main_menu_keyboard
from loader import logger

# Эта функция универсальна и не требует изменений.
def format_traffic(byte_count: int | None) -> str:
    """Красиво форматирует байты в Кб, Мб, Гб."""
    if byte_count is None:
        return "Неизвестно"
    if byte_count == 0:
        return "0 Гб"
    
    power = 1024
    n = 0
    power_labels = {0: 'Б', 1: 'Кб', 2: 'Мб', 3: 'Гб'}
    while byte_count >= power and n < len(power_labels) - 1:
        byte_count /= power
        n += 1
    return f"{byte_count:.2f} {power_labels.get(n, 'Тб')}"

# Эта функция универсальна и не требует изменений.
def decline_word(number: int, titles: list[str]) -> str:
    """Правильно склоняет слово после числа."""
    if (number % 10 == 1) and (number % 100 != 11):
        return titles[0]
    elif (number % 10 in [2, 3, 4]) and (number % 100 not in [12, 13, 14]):
        return titles[1]
    else:
        return titles[2]

# --- ОСНОВНАЯ АДАПТАЦИЯ ---
async def get_xui_user_info(event: types.Message | types.CallbackQuery, xui: XUIClient):
    """
    Универсальная функция для получения данных пользователя из БД и 3x-ui панели. # <-- ИЗМЕНЕНИЕ в докстринге
    Возвращает кортеж (user_from_db, xui_user_object).
    В случае ошибки отправляет сообщение пользователю и возвращает (user_from_db, None).
    """
    user_id = event.from_user.id
    user = await db.get_user(user_id) # <-- Предполагаем, что ваша функция DB асинхронна

    async def send_or_edit(text, reply_markup):
        """Отправляет или редактирует сообщение в зависимости от типа события."""
        if isinstance(event, types.CallbackQuery):
            try:
                # Проверяем, что сообщение не совпадает, чтобы избежать ошибки
                if event.message.text != text:
                    await event.message.edit_text(text, reply_markup=reply_markup)
                else:
                    await event.answer() # Просто закрываем "часики" на кнопке
            except TelegramBadRequest:
                await event.message.delete()
                await event.message.answer(text, reply_markup=reply_markup)
        else:
            await event.answer(text, reply_markup=reply_markup)

    # ВАЖНО: Предполагается, что в вашей модели user в БД поле называется xui_username
    if not user or not user.xui_username: # <-- ИЗМЕНЕНИЕ: marzban_username -> xui_username
        await send_or_edit(
            "У вас еще нет активной подписки. Пожалуйста, оплатите тариф, чтобы получить доступ.",
            back_to_main_menu_keyboard()
        )
        return user, None

    try:
        # Вызываем метод нашего нового клиента
        xui_user = await xui.get_user(user.xui_username) # <-- ИЗМЕНЕНИЕ: marzban -> xui
        if not xui_user:
            # Текст ошибки теперь тоже соответствует действительности
            raise ValueError("User not found in 3x-ui panel") # <-- ИЗМЕНЕНИЕ
        
        return user, xui_user
        
    except Exception as e:
        logger.error(f"Failed to get user {user.xui_username} from 3x-ui: {e}", exc_info=True) # <-- ИЗМЕНЕНИЕ
        await send_or_edit(
            "Не удалось получить данные о вашей подписке. Пожалуйста, обратитесь в поддержку.",
            back_to_main_menu_keyboard()
        )
        return user, None


# Эта функция идеально подходит, нужно лишь поменять комментарий
def get_user_attribute(user_obj, key, default=None):
    """Безопасно получает атрибут из объекта 3x-ui (объекта или словаря).""" # <-- ИЗМЕНЕНИЕ в докстринге
    if isinstance(user_obj, dict):
        return user_obj.get(key, default)
    return getattr(user_obj, key, default)