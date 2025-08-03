# tgbot/services/utils.py (ПРАВИЛЬНАЯ ВЕРСИЯ)

from datetime import datetime
from marzban.init_client import MarzClientCache
from database import requests as db
from aiogram import types
# Импортируем клавиатуру напрямую, чтобы не зависеть от хендлеров
from tgbot.keyboards.inline import back_to_main_menu_keyboard
from loader import logger


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

def decline_word(number: int, titles: list[str]) -> str:
    """
    Правильно склоняет слово после числа.
    Пример: decline_word(5, ['день', 'дня', 'дней']) -> 'дней'
    :param number: Число.
    :param titles: Список из трех вариантов слова (для 1, 2, 5).
    """
    if (number % 10 == 1) and (number % 100 != 11):
        return titles[0]
    elif (number % 10 in [2, 3, 4]) and (number % 100 not in [12, 13, 14]):
        return titles[1]
    else:
        return titles[2]

async def get_marzban_user_info(event: types.Message | types.CallbackQuery, marzban: MarzClientCache):
    """
    Универсальная функция для получения данных пользователя из БД и Marzban.
    Возвращает кортеж (user_from_db, marzban_user_object).
    В случае ошибки отправляет сообщение пользователю и возвращает (user_from_db, None).
    """
    user_id = event.from_user.id
    user = db.get_user(user_id)

    # --- УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТПРАВКИ/РЕДАКТИРОВАНИЯ СООБЩЕНИЙ ---
    async def send_or_edit(text, reply_markup):
        """Отправляет или редактирует сообщение в зависимости от типа события."""
        if isinstance(event, types.CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=reply_markup)
            except TelegramBadRequest:
                # Если не вышло отредактировать, удаляем и шлем новое
                await event.message.delete()
                await event.message.answer(text, reply_markup=reply_markup)
        else:
            await event.answer(text, reply_markup=reply_markup)

    # --- ПРОВЕРКИ ---
    if not user or not user.marzban_username:
        await send_or_edit(
            "У вас еще нет активной подписки. Пожалуйста, оплатите тариф, чтобы получить доступ.",
            back_to_main_menu_keyboard()
        )
        return user, None

    try:
        marzban_user = await marzban.get_user(user.marzban_username)
        if not marzban_user:
            raise ValueError("User not found in Marzban panel")
        
        # Если все успешно, возвращаем данные
        return user, marzban_user
        
    except Exception as e:
        logger.error(f"Failed to get user {user.marzban_username} from Marzban: {e}", exc_info=True)
        await send_or_edit(
            "Не удалось получить данные о вашей подписке. Пожалуйста, обратитесь в поддержку.",
            back_to_main_menu_keyboard()
        )
        return user, None


def get_user_attribute(user_obj, key, default=None):
    """Безопасно получает атрибут из объекта Marzban (словаря или объекта)."""
    if isinstance(user_obj, dict):
        return user_obj.get(key, default)
    return getattr(user_obj, key, default)