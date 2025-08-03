# tgbot/handlers/admin/broadcast.py

import asyncio
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from loader import logger

# --- Фильтры, клавиатуры, БД ---
from tgbot.filters.admin import IsAdmin
from database import requests as db
from tgbot.keyboards.inline import confirm_broadcast_keyboard, cancel_fsm_keyboard, admin_main_menu_keyboard

admin_broadcast_router = Router()
admin_broadcast_router.message.filter(IsAdmin())
admin_broadcast_router.callback_query.filter(IsAdmin())


# --- Состояния FSM для рассылки ---
class BroadcastFSM(StatesGroup):
    get_message = State()
    confirm = State()


# --- Обработчик для кнопки "Отмена" внутри FSM ---
@admin_broadcast_router.callback_query(F.data == "admin_main_menu", BroadcastFSM.get_message)
@admin_broadcast_router.callback_query(F.data == "admin_main_menu", BroadcastFSM.confirm)
async def cancel_broadcast_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Рассылка отменена.", reply_markup=admin_main_menu_keyboard())


# --- Начало сценария рассылки ---
@admin_broadcast_router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    """Шаг 1: Запрашиваем сообщение для рассылки."""
    await call.message.edit_text(
        "Пришлите сообщение, которое вы хотите разослать всем пользователям.\n\n"
        "Вы можете присылать текст, фото, видео, документы и использовать форматирование.",
        reply_markup=cancel_fsm_keyboard("admin_main_menu")
    )
    await state.set_state(BroadcastFSM.get_message)


# --- Получение сообщения и запрос подтверждения ---
@admin_broadcast_router.message(BroadcastFSM.get_message)
async def get_broadcast_message(message: Message, state: FSMContext):
    """Шаг 2: Получаем сообщение, показываем его для предпросмотра и запрашиваем подтверждение."""
    # Сохраняем все сообщение целиком, чтобы можно было его скопировать
    # Это позволяет сохранить фото, видео, кнопки и т.д.
    await state.update_data(message_to_send=message)
    
    # Отправляем сообщение "для предпросмотра"
    await message.answer(
        "Вот так будет выглядеть ваше сообщение для рассылки. Вы уверены, что хотите его отправить?",
        reply_markup=confirm_broadcast_keyboard()
    )
    await state.set_state(BroadcastFSM.confirm)


# --- Запуск рассылки после подтверждения ---
@admin_broadcast_router.callback_query(F.data == "broadcast_start", BroadcastFSM.confirm)
async def confirm_and_run_broadcast(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Шаг 3: Запускаем процесс рассылки."""
    data = await state.get_data()
    message_to_send: Message = data.get("message_to_send")
    await state.clear()

    if not message_to_send:
        await call.message.edit_text(
            "❌ <b>Ошибка:</b> не найдено сообщение для рассылки. Попробуйте снова.",
            reply_markup=admin_main_menu_keyboard(),
            parse_mode="HTML"
        )
        return

    users_ids = db.get_all_users_ids()
    total_users = len(users_ids)
    
    await call.message.edit_text(
        f"🚀 <b>Рассылка запущена!</b>\n\n"
        f"Сообщение будет отправлено <b>{total_users}</b> пользователям. "
        "Это может занять некоторое время. Вы получите отчет по завершении.",
        reply_markup=None,
        parse_mode="HTML"
    )

    # --- Сам процесс рассылки ---
    success_count = 0
    errors_count = 0
    
    for user_id in users_ids:
        try:
            await message_to_send.copy_to(chat_id=user_id)
            success_count += 1
            await asyncio.sleep(0.025)
        except Exception as e:
            errors_count += 1
            logger.warning(f"Broadcast failed for user {user_id}. Error: {e}")
            
    # --- Финальный отчет админу ---
    await call.bot.send_message(
        chat_id=call.from_user.id,
        text=(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"👍 Отправлено: <b>{success_count}</b>\n"
            f"👎 Ошибок: <b>{errors_count}</b>"
        ),
    )
