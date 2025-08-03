import time
from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from loader import logger, config
from database import requests as db
from tgbot.keyboards.inline import close_support_chat_keyboard, main_menu_keyboard
from tgbot.states.support_states import SupportFSM
from tgbot.middlewares.support_timeout import SupportTimeoutMiddleware

support_router = Router()
support_router.message.middleware(SupportTimeoutMiddleware())
support_router.callback_query.middleware(SupportTimeoutMiddleware())



# =============================================================================
# --- БЛОК 1: ВХОД В РЕЖИМ ПОДДЕРЖКИ ---
# =============================================================================

def support_intro_keyboard():
    """Клавиатура с одной кнопкой 'Начать диалог'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Начать диалог с поддержкой", callback_data="confirm_start_support")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

async def show_support_intro(event: types.Message | types.CallbackQuery):
    """Показывает приветственное сообщение поддержки."""
    text = (
        "💬 <b>Поддержка</b>\n\n"
        "Если у вас возникли вопросы или проблемы, вы можете связаться с нашей службой поддержки.\n\n"
        "Нажмите кнопку ниже, чтобы начать диалог."
    )
    reply_markup = support_intro_keyboard()

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup)
    else:
        await event.answer(text, reply_markup=reply_markup)

@support_router.message(Command("support"))
async def support_command_handler(message: types.Message):
    """Хендлер для команды /support."""
    await show_support_intro(message)

@support_router.callback_query(F.data == "support_chat_start")
async def support_callback_handler(call: types.CallbackQuery):
    """Хендлер для кнопки 'Поддержка' из главного меню."""
    await call.answer()
    await show_support_intro(call)


# =============================================================================
# --- БЛОК 2: УПРАВЛЕНИЕ ДИАЛОГОМ (ДЛЯ ПОЛЬЗОВАТЕЛЯ) ---
# =============================================================================

@support_router.callback_query(F.data == "confirm_start_support")
async def start_support_chat_confirmed(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Создает тему и переводит пользователя в режим чата после подтверждения."""
    await state.clear()
    user_id = call.from_user.id
    user = db.get_user(user_id)

    if user and user.support_topic_id:
        text = "Вы уже находитесь в чате с поддержкой. Просто продолжайте писать сообщения ниже."
    else:
        try:
            topic = await bot.create_forum_topic(
                chat_id=config.tg_bot.support_chat_id,
                name=f"Тикет #{user_id} | @{call.from_user.username or 'NoUsername'}"
            )
            db.set_user_support_topic(user_id, topic.message_thread_id)
            await bot.send_message(
                chat_id=config.tg_bot.support_chat_id,
                message_thread_id=topic.message_thread_id,
                text=f"👤 Пользователь <b>{call.from_user.full_name}</b> (ID: <code>{user_id}</code>) открыл новый тикет."
            )
            text = "Вы начали диалог с поддержкой. Опишите вашу проблему, и вам скоро ответят."
        except Exception as e:
            logger.error(f"Failed to create support topic for user {user_id}: {e}", exc_info=True)
            await call.answer("Не удалось создать чат с поддержкой. Попробуйте позже.", show_alert=True)
            return

    await state.set_state(SupportFSM.in_chat)
    await state.update_data(last_activity_time=time.time())
    
    await call.message.edit_text(text, reply_markup=close_support_chat_keyboard())
    await call.answer()


@support_router.callback_query(F.data == "support_chat_close", SupportFSM.in_chat)
async def close_support_chat_by_user(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обрабатывает закрытие диалога со стороны пользователя."""
    await state.clear()
    user = db.get_user(call.from_user.id)
    if user and user.support_topic_id:
        await bot.send_message(
            chat_id=config.tg_bot.support_chat_id,
            message_thread_id=user.support_topic_id,
            text="💬 Пользователь завершил диалог."
        )
    db.clear_user_support_topic(call.from_user.id)
    await call.message.edit_text(
        "✅ <b>Диалог с поддержкой завершен.</b>\n\nВы вернулись в главное меню.", 
        reply_markup=main_menu_keyboard()
    )


@support_router.message(SupportFSM.in_chat, Command("cancel"))
async def cancel_support_from_command(message: types.Message, state: FSMContext, bot: Bot):
    """Позволяет пользователю выйти из чата поддержки командой /cancel."""
    # Создаем фейковый колбэк, чтобы вызвать логику кнопки "Завершить диалог"
    fake_call = types.CallbackQuery(id="fake_call", from_user=message.from_user, chat_instance="", message=message)
    await close_support_chat_by_user(fake_call, state, bot)
    await message.delete() # Удаляем сообщение /cancel


@support_router.message(SupportFSM.in_chat)
async def process_message_in_support_chat(message: Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает все сообщения от пользователя, находящегося в состоянии чата с поддержкой.
    Если это команда - выходит из чата.
    Если это обычное сообщение - пересылает в поддержку.
    """
    
    # 1. Проверяем, является ли сообщение командой
    if message.text and message.text.startswith('/'):
        # Если это команда, выходим из режима поддержки
        await state.clear()
        await message.answer(
        "<b>Вы вышли из режима чата с поддержкой.</b>\n\n"
        "Ваша команда не была выполнена. Пожалуйста, отправьте ее еще раз, чтобы бот мог ее обработать.",
        reply_markup=main_menu_keyboard()
    )

        return # Завершаем выполнение хендлера

    # 2. Если это не команда, обрабатываем как обычное сообщение для поддержки
    user = db.get_user(message.from_user.id)
    if not user or not user.support_topic_id:
        await state.clear()
        await message.answer("Произошла ошибка. Пожалуйста, начните чат с поддержкой заново.", reply_markup=main_menu_keyboard())
        return

    # Пересылаем сообщение админу
    await message.forward(
        chat_id=config.tg_bot.support_chat_id,
        message_thread_id=user.support_topic_id
    )


# =============================================================================
# --- БЛОК 3: ОБРАБОТКА ОТВЕТОВ ИЗ ГРУППЫ ПОДДЕРЖКИ (ДЛЯ АДМИНА) ---
# =============================================================================

@support_router.message(F.chat.id == config.tg_bot.support_chat_id, F.message_thread_id, Command("close"))
async def admin_close_topic_command(message: types.Message, bot: Bot):
    """Закрывает тикет по команде /close от админа."""
    user_to_reply = db.get_user_by_support_topic(message.message_thread_id)
    if not user_to_reply:
        await message.reply("Не удалось найти пользователя для этой темы.")
        return

    try:
        await bot.send_message(
            user_to_reply.user_id, 
            "Оператор поддержки завершил ваш диалог. Если у вас возникнут новые вопросы, вы всегда можете открыть новый тикет.\n"
            "Вы были возвращены в главное меню!",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.warning(f"Could not send '/close' notification to user {user_to_reply.user_id}: {e}")
    
    db.clear_user_support_topic(user_to_reply.user_id)
    await bot.close_forum_topic(config.tg_bot.support_chat_id, message.message_thread_id)
    await message.reply("✅ Тикет успешно закрыт.")


@support_router.message(F.chat.id == config.tg_bot.support_chat_id, F.message_thread_id)
async def admin_reply_to_user_from_topic(message: types.Message, bot: Bot):
    """
    Пересылает ответ админа пользователю с припиской "Ответ от поддержки".
    """
    # Игнорируем сообщения от самого бота
    if message.from_user.id == bot.id:
        return

    user_to_reply = db.get_user_by_support_topic(message.message_thread_id)
    if not user_to_reply:
        return

    try:
        # Формируем нашу "шапку" для сообщения
        header = "💬 <b>Ответ от поддержки:</b>\n\n"
        
        # 1. Если админ отправил только текст
        if message.text:
            # Просто соединяем нашу шапку и текст админа
            await bot.send_message(
                chat_id=user_to_reply.user_id,
                text=header + message.text,
                reply_markup=message.reply_markup # Копируем кнопки, если они были
            )
            
        # 2. Если админ отправил фото, видео, документ и т.д. с подписью (caption)
        elif message.caption:
            # Копируем сообщение, но изменяем его подпись, добавляя нашу шапку
            await message.copy_to(
                chat_id=user_to_reply.user_id,
                caption=header + message.caption,
                # caption_entities нужно очистить, т.к. мы меняем текст.
                # Aiogram сам создаст новые entities для нашего HTML
            )
            
        # 3. Если админ отправил медиа БЕЗ подписи
        else:
            # Сначала отправляем нашу "шапку" отдельным сообщением
            await bot.send_message(
                chat_id=user_to_reply.user_id,
                text=header
            )
            # А затем копируем медиафайл без изменений
            await message.copy_to(chat_id=user_to_reply.user_id)

    except Exception as e:
        logger.error(f"Failed to send admin's reply to user {user_to_reply.user_id}: {e}", exc_info=True)
        await message.reply(f"❌ Не удалось отправить ответ пользователю. Ошибка: {e}")