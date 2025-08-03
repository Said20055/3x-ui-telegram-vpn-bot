# tgbot/handlers/user/start.py (Полная версия)

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
# --- Импорты ---
from loader import logger
from database import requests as db
from marzban.init_client import MarzClientCache
from tgbot.keyboards.inline import main_menu_keyboard, back_to_main_menu_keyboard

# Создаем локальный роутер для этого файла
start_router = Router()

# =============================================================================
# --- БЛОК: СТАРТ БОТА И РЕФЕРАЛЬНАЯ ССЫЛКА ---
# =============================================================================

@start_router.message(CommandStart())
async def process_start_command(message: Message, command: CommandObject, bot: Bot, marzban: MarzClientCache):
    """
    Единый обработчик команды /start.
    Регистрирует пользователя и обрабатывает реферальные ссылки.
    """
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    
    # 1.1. Регистрируем или получаем пользователя
    user, created = db.get_or_create_user(user_id, full_name, username)

    # 1.2. Обрабатываем реферальную ссылку, если она есть
    if command and command.args and command.args.startswith('ref'):
        if created:
            # Если пользователь новый, пытаемся начислить бонус
            referrer_id = None
            try:
                potential_referrer_id = int(command.args[3:])
                if potential_referrer_id != user_id and db.get_user(potential_referrer_id):
                    referrer_id = potential_referrer_id
            except (ValueError, IndexError, TypeError): pass

            if referrer_id:
                # Начисляем бонус, если реферер найден
                await activate_referral_bonus(message, referrer_id, marzban, bot)
        else:
            # Если пользователь не новый, сообщаем ему об этом
            await message.answer("Вы уже зарегистрированы. Реферальная ссылка работает только для новых пользователей.")
    
    # 1.3. Показываем информативное приветственное сообщение
    welcome_text = (
        f"👋 Добро пожаловать, <b>{full_name}</b>!\n\n"
        "Я ваш персональный помощник для доступа к быстрому и безопасному VPN.\n\n"
        "<b>Что я умею:</b>\n"
        "🔹 <b>Мой профиль</b> - проверьте статус подписки и получите ключ.\n"
        "🔹 <b>Оплатить</b> - выберите удобный тариф и продлите доступ.\n"
        "🔹 <b>Инструкция</b> - узнайте, как настроить VPN на вашем устройстве.\n\n"
        "Используйте кнопки ниже для навигации."
    )
    await message.answer(welcome_text, reply_markup=main_menu_keyboard())


async def activate_referral_bonus(message: Message, referrer_id: int, marzban: MarzClientCache, bot: Bot):
    """Вспомогательная функция для активации реферального бонуса."""
    user_id = message.from_user.id
    bonus_days = 3
    marzban_username = f"user_{user_id}"
    try:
        await marzban.add_user(username=marzban_username, expire_days=bonus_days)
        logger.info(f"Successfully created Marzban user '{marzban_username}' with {bonus_days} bonus days.")
        
        # Обновляем наши БД
        db.set_user_referrer(user_id, referrer_id)
        db.update_user_marzban_username(user_id, marzban_username)
        db.extend_user_subscription(user_id, days=bonus_days)
        
        await message.answer(f"🎉 Вы пришли по приглашению и получили <b>пробную подписку на {bonus_days} дня</b>!")
        
        # Уведомляем реферера
        try:
            await bot.send_message(referrer_id, f"По вашей ссылке зарегистрировался новый пользователь: {message.from_user.full_name}!")
        except Exception as e:
            logger.error(f"Could not send notification to referrer {referrer_id}: {e}")
            
    except Exception as e:
        logger.error(f"Failed to create Marzban user for referral bonus for user {user_id}: {e}", exc_info=True)
        await message.answer("Произошла ошибка при активации вашего стартового бонуса. Пожалуйста, обратитесь в поддержку.")
# =============================================================================
# --- БЛОК: ОТОБРАЖЕНИЕ РЕФЕРАЛЬНОЙ ПРОГРАММЫ ---
# =============================================================================

async def show_referral_info(message: Message, bot: Bot):
    """Вспомогательная функция для показа информации о реферальной программе."""
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    user_data = db.get_user(user_id)
    referral_count = db.count_user_referrals(user_id)

    text = (
        "🤝 <b>Ваша реферальная программа</b>\n\n"
        "Приглашайте друзей и получайте за это приятные бонусы!\n\n"
        "🔗 <b>Ваша персональная ссылка для приглашений:</b>\n"
        f"<code>{referral_link}</code>\n"
        "<i>(нажмите, чтобы скопировать)</i>\n\n"
        f"👤 <b>Вы пригласили:</b> {referral_count} чел.\n"
        f"🎁 <b>Ваши бонусные дни:</b> {user_data.referral_bonus_days if user_data else 0} дн.\n\n"
        "Вы будете получать <b>7 бонусных дней</b> за каждую первую оплату подписки вашим другом."
    )
    
    # Если это колбэк, редактируем сообщение. Если команда - отправляем новое.
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=back_to_main_menu_keyboard())
    else:
        await message.answer(text, reply_markup=back_to_main_menu_keyboard())

# Хендлер для команды /referral
@start_router.message(Command("referral"))
async def referral_command_handler(message: Message, bot: Bot):
    await show_referral_info(message, bot)

# Хендлер для кнопки "Реферальная программа"
@start_router.callback_query(F.data == "referral_program")
async def referral_program_handler(call: CallbackQuery, bot: Bot):
    await call.answer()
    await show_referral_info(call, bot)
    
@start_router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu_handler(call: CallbackQuery, state: FSMContext):
    """Возвращает пользователя в главное меню."""
    await state.clear()
    await call.answer()
    text = f'👋 Привет, {call.from_user.full_name}!'
    reply_markup = main_menu_keyboard()

    # Надежная логика редактирования/отправки
    try:
        # Пытаемся отредактировать, это самый красивый вариант
        await call.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        # Если не вышло (например, это было сообщение с фото), удаляем и шлем новое
        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass # Если не можем удалить - не страшно
        await call.message.answer(text, reply_markup=reply_markup)