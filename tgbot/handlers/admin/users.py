# tgbot/handlers/admin/users.py

import asyncio
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from loader import logger

# --- Фильтры и Клавиатуры ---
from tgbot.filters.admin import IsAdmin
from tgbot.keyboards.inline import user_manage_keyboard, confirm_delete_keyboard, back_to_main_menu_keyboard, back_to_admin_main_menu_keyboard

# --- База данных и API ---
from database import requests as db
# --- ИЗМЕНЕНИЕ: Импортируем наш новый клиент ---
from xui.init_client import XUIClient


admin_users_router = Router()
# Применяем фильтр админа ко всем хендлерам в этом роутере
admin_users_router.message.filter(IsAdmin())
admin_users_router.callback_query.filter(IsAdmin())


# --- Состояния FSM (без изменений) ---
class AdminFSM(StatesGroup):
    find_user = State()
    add_days_user_id = State()
    add_days_amount = State()


# =============================================================================
# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ---
# =============================================================================

async def show_user_card(message_or_call, user_id: int):
    """
    Отображает карточку пользователя с информацией и кнопками управления.
    """
    # Предполагается, что ваши функции DB асинхронны. Если нет - уберите await
    user = await db.get_user(user_id) 
    if not user:
        text = "Пользователь не найден."
        reply_markup = back_to_main_menu_keyboard()
    else:
        sub_end_str = user.subscription_end_date.strftime('%d.%m.%Y %H:%M') if user.subscription_end_date else "Отсутствует"
        text = (
            f"<b>Пользователь найден:</b>\n\n"
            f"<b>ID:</b> <code>{user.user_id}</code>\n"
            f"<b>Username:</b> @{user.username or 'Отсутствует'}\n"
            f"<b>Имя:</b> {user.full_name}\n\n"
            f"<b>Подписка до:</b> {sub_end_str}\n"
            # --- ИЗМЕНЕНИЕ: Обновили название поля для консистентности ---
            f"<b>3x-ui аккаунт:</b> <code>{user.xui_username or 'Не создан'}</code>"
        )
        reply_markup = user_manage_keyboard(user.user_id)

    if isinstance(message_or_call, CallbackQuery):
        try:
            await message_or_call.message.edit_text(text, reply_markup=reply_markup)
        except:
            await message_or_call.bot.send_message(message_or_call.from_user.id, text, reply_markup=reply_markup)
    else:
        await message_or_call.answer(text, reply_markup=reply_markup)


# =============================================================================
# --- ОСНОВНЫЕ ХЕНДЛЕРЫ ---
# =============================================================================

@admin_users_router.callback_query(F.data == "admin_users_menu")
async def users_menu(call: CallbackQuery, state: FSMContext):
    """Меню поиска пользователя."""
    await state.clear()
    await call.message.edit_text(
        "<b>👤 Управление пользователями</b>\n\n"
        "Введите ID или username (без @) пользователя для поиска:",
        reply_markup=back_to_admin_main_menu_keyboard()
    )
    await state.set_state(AdminFSM.find_user)


@admin_users_router.message(AdminFSM.find_user)
async def find_user(message: Message, state: FSMContext):
    """Находит пользователя по ID или username и показывает его карточку."""
    await state.clear()
    query = message.text.strip()
    user = None

    if query.isdigit():
        user = await db.get_user(int(query))
    else:
        user = await db.get_user_by_username(query.replace("@", ""))
    
    if not user:
        await message.answer("Пользователь с таким ID или username не найден в базе данных бота.\n\n"
                             "Попробуйте еще раз:")
        await state.set_state(AdminFSM.find_user)
        return
        
    await show_user_card(message, user.user_id)


# --- Блок добавления дней ---

@admin_users_router.callback_query(F.data.startswith("admin_add_days_"))
async def add_days_start(call: CallbackQuery, state: FSMContext):
    """Начало сценария добавления дней подписки."""
    user_id = int(call.data.split("_")[3])
    await state.update_data(user_id=user_id)
    
    await call.message.edit_text(f"Введите количество дней для добавления пользователю <code>{user_id}</code>:")
    await state.set_state(AdminFSM.add_days_amount)


@admin_users_router.message(AdminFSM.add_days_amount)
# --- ИЗМЕНЕНИЕ: Получаем наш новый клиент XUIClient ---
async def add_days_finish(message: Message, state: FSMContext, xui: XUIClient, bot: Bot):
    """
    Завершение сценария добавления дней подписки.
    Продлевает подписку или создает нового пользователя в 3x-ui.
    """
    
    # 1. Валидация ввода (без изменений)
    try:
        days_to_add = int(message.text)
        if days_to_add <= 0:
            await message.answer("❌ <b>Ошибка:</b> Введите целое положительное число.")
            return
    except (ValueError, TypeError):
        await message.answer("❌ <b>Ошибка:</b> Пожалуйста, введите корректное число.")
        return

    # 2. Получение данных (без изменений)
    data = await state.get_data()
    user_id = data.get("user_id")
    await state.clear()
    
    await message.answer(f"⏳ Продлеваю/создаю подписку для пользователя <code>{user_id}</code> на <b>{days_to_add}</b> дн...")

    user = await db.get_user(user_id)
    if not user:
        await message.answer(f"Не удалось найти пользователя <code>{user_id}</code> в базе.")
        return
        
    # --- ИЗМЕНЕНИЕ: Основная логика адаптирована под XUIClient ---
    xui_username = (user.xui_username or f"user_{user_id}").lower()

    try:
        # Вызываем наш "умный" метод, который сам решает, создать или продлить.
        # Метод вернет ключ, но он нам здесь не нужен. Главное - что он отработал.
        result = await xui.modify_user(username=xui_username, expire_days=days_to_add)

        if not result:
            # Если метод вернул None, значит произошла ошибка внутри клиента
            await message.answer(f"❌ Произошла ошибка при взаимодействии с 3x-ui для пользователя <code>{user_id}</code>. Проверьте логи.")
            return

        # Если у пользователя не было xui_username, значит, мы его только что создали.
        if not user.xui_username:
            await db.update_user_xui_username(user_id, xui_username)
            logger.info(f"Admin CREATED and subscribed 3x-ui user '{xui_username}' for {days_to_add} days.")
        else:
            logger.info(f"Admin EXTENDED subscription for 3x-ui user '{xui_username}' by {days_to_add} days.")

        # Обновляем дату подписки в нашей БД.
        await db.extend_user_subscription(user_id, days=days_to_add)
        
        # Получаем обновленные данные для отчета.
        updated_user = await db.get_user(user_id)
        new_sub_end_date = updated_user.subscription_end_date.strftime('%d.%m.%Y')
        
        # 4. Отправляем отчеты об успехе (без изменений)
        await message.answer(
            f"✅ <b>Успешно!</b>\n\n"
            f"Пользователю <code>{user_id}</code> добавлено <b>{days_to_add}</b> дн.\n"
            f"Новая дата окончания подписки: <b>{new_sub_end_date}</b>"
        )
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"🎉 Администратор продлил вашу подписку на <b>{days_to_add}</b> дн.!\n"
                     f"Новая дата окончания: <b>{new_sub_end_date}</b>"
            )
        except Exception as e:
            logger.warning(f"Could not send notification to user {user_id}: {e}")
            await message.answer("❗️Не удалось уведомить пользователя.")

    except Exception as e:
        logger.error(f"Admin failed to add days for user {user_id}: {e}", exc_info=True)
        await message.answer(f"❌ Произошла критическая ошибка при обработке запроса для пользователя <code>{user_id}</code>.")
    
    await show_user_card(message, user_id)

# --- Блок удаления пользователя ---

@admin_users_router.callback_query(F.data.startswith("admin_delete_user_"))
async def delete_user_confirm(call: CallbackQuery):
    """Запрашивает подтверждение на удаление."""
    user_id = int(call.data.split("_")[3])
    await call.message.edit_text(
        f"Вы уверены, что хотите полностью удалить пользователя <code>{user_id}</code>?\n\n"
        "<b>Это действие необратимо.</b> Пользователь будет удален из 3x-ui и из базы данных бота.",
        reply_markup=confirm_delete_keyboard(user_id)
    )

@admin_users_router.callback_query(F.data.startswith("admin_confirm_delete_user_"))
# --- ИЗМЕНЕНИЕ: Получаем наш новый клиент XUIClient ---
async def delete_user_finish(call: CallbackQuery, xui: XUIClient):
    await call.answer("Удаляю пользователя...")
    
    try:
        user_id = int(call.data.split("_")[4])
        user = await db.get_user(user_id)
        
        if not user:
            await call.message.edit_text(f"Пользователь <code>{user_id}</code> уже был удален или не найден.")
            return

        xui_deletion_success = False
        if user.xui_username:
            logger.info(f"Admin is deleting user '{user.xui_username}' from 3x-ui")
            xui_deletion_success = await xui.delete_user(user.xui_username)
        else:
            xui_deletion_success = True # Если в 3x-ui и не было, считаем успехом

        if xui_deletion_success:
            await db.delete_user(user.user_id)
            await call.message.edit_text(f"✅ Пользователь <code>{user_id}</code> успешно удален.")
        else:
            await call.message.edit_text(f"❌ **Ошибка!**\n\nНе удалось удалить пользователя из 3x-ui. Проверьте логи панели.")

    except Exception as e:
        logger.error(f"Unexpected error in delete_user_finish for call {call.data}: {e}", exc_info=True)
        await call.message.edit_text("❌ Произошла непредвиденная ошибка в процессе удаления.")

# --- Хендлер для возврата к карточке пользователя ---
@admin_users_router.callback_query(F.data.startswith("admin_show_user_"))
async def show_user_handler(call: CallbackQuery):
    """Показывает карточку пользователя (нужно для кнопки 'Отмена' при удалении)."""
    user_id = int(call.data.split("_")[3])
    await show_user_card(call, user_id)