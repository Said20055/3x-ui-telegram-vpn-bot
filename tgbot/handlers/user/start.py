# tgbot/handlers/user/start.py

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
# --- Импорты ---
from loader import logger
from database import requests as db
# --- ИЗМЕНЕНИЕ: Импортируем наш новый XUIClient ---
from xui.init_client import XUIClient
from tgbot.services.subscription import check_subscription
from tgbot.keyboards.inline import main_menu_keyboard, back_to_main_menu_keyboard, channels_subscribe_keyboard

# Создаем локальный роутер для этого файла
start_router = Router()

# =============================================================================
# --- БЛОК: СТАРТ БОТА И РЕФЕРАЛЬНАЯ ССЫЛКА ---
# =============================================================================

async def give_trial_subscription(user_id: int, bot: Bot, xui: XUIClient, chat_id: int):
    """
    Создает пользователя в 3x-ui на 14 дней, обновляет БД и отправляет сообщение.
    Принимает только ID, чтобы быть полностью независимой.
    """
    trial_days = 14
    xui_username = f"user_{user_id}"
    
    try:
        # 1. Создаем пользователя в панели 3x-ui
        result_uuid = await xui.add_user(username=xui_username, expire_days=trial_days)
        if not result_uuid:
            raise Exception("XUIClient failed to create user.")

        logger.info(f"Successfully created 3x-ui user '{xui_username}' with {trial_days} trial days for user {user_id}.")

        # 2. Обновляем нашу базу данных
        await db.update_user_xui_username(user_id, xui_username)
        await db.extend_user_subscription(user_id, days=trial_days)
        await db.set_trial_received(user_id)

        # 3. Отправляем поздравительное сообщение
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"Вы получили пробную подписку на <b>{trial_days} дней</b>.\n"
                "Чтобы увидеть ваш ключ-конфиг и статус подписки, нажмите кнопку «👤 Мой профиль» в меню ниже."
            ),
            reply_markup=main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Failed to give trial subscription to user {user_id}: {e}", exc_info=True)
        await bot.send_message(chat_id, "❌ Произошла ошибка при активации вашего пробного периода. Пожалуйста, обратитесь в поддержку.")


# --- ГЛАВНЫЙ ХЕНДЛЕР КОМАНДЫ /start ---
@start_router.message(CommandStart())
async def process_start_command(message: Message, command: CommandObject, bot: Bot):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    
    user, created = await db.get_or_create_user(user_id, full_name, username)

    # --- ОБРАБОТКА РЕФЕРАЛЬНОЙ ССЫЛКИ (НЕЗАВИСИМО) ---
    if created and command and command.args and command.args.startswith('ref'):
        # ... (этот блок остается без изменений) ...
        try:
            referrer_id = int(command.args[3:])
            if referrer_id != user_id and await db.get_user(referrer_id):
                await db.set_user_referrer(user_id, referrer_id)
                logger.info(f"User {user_id} was referred by {referrer_id}.")
                try:
                    await bot.send_message(referrer_id, f"По вашей ссылке зарегистрировался новый пользователь: {full_name}!")
                except Exception: pass
        except (ValueError, IndexError, TypeError): pass

    # --- СЦЕНАРИЙ ДЛЯ НОВОГО ПОЛЬЗОВАТЕЛЯ ---
    if created:
        welcome_text = (
            f"👋 <b>Добро пожаловать, {full_name}!</b>\n\n"
            "Я — ваш персональный VPN-бот, созданный для обеспечения быстрой, безопасной и анонимной работы в интернете.\n\n"
            "<b>Что вы получаете:</b>\n"
            "🔹 Высокая скорость и стабильное соединение.\n"
            "🔹 Защита от блокировок и цензуры.\n"
            "🔹 Полная анонимность вашего трафика.\n\n"
            "Чтобы вы могли оценить все преимущества, мы дарим вам <b>бесплатный пробный период на 2 недели!</b>"
        )
        await message.answer(welcome_text, reply_markup=main_menu_keyboard())
        return

    # --- СЦЕНАРИЙ ДЛЯ СТАРОГО ПОЛЬЗОВАТЕЛЯ ---
    await message.answer(f"👋 С возвращением, <b>{full_name}</b>!", reply_markup=main_menu_keyboard())


# --- НОВЫЙ ХЕНДЛЕР ДЛЯ КНОПКИ "ПОЛУЧИТЬ БЕСПЛАТНО" ---
@start_router.callback_query(F.data == "start_trial_process")
async def start_trial_process_handler(call: CallbackQuery, bot: Bot, xui: XUIClient):
    """
    Запускает процесс получения пробной подписки после нажатия на кнопку.
    Включает проверку на повторное получение.
    """
    user_id = call.from_user.id
    
    # --- НОВАЯ, ВАЖНАЯ ПРОВЕРКА ---
    # 1. Получаем пользователя из БД
    user = await db.get_user(user_id)
    
    # 2. Проверяем, получал ли он уже триал
    if user and user.has_received_trial:
        await call.answer("Вы уже использовали свой пробный период.", show_alert=True)
        # Заменяем приветственное сообщение на стандартное главное меню
        await call.message.edit_text(
            f"👋 Добро пожаловать, <b>{call.from_user.full_name}</b>!",
            reply_markup=main_menu_keyboard()
        )
        return # Прерываем выполнение функции

    # --- Остальная логика остается без изменений ---
    # 3. Проверяем подписку на каналы
    is_subscribed = await check_subscription(bot, user_id)
    if is_subscribed:
        # Если подписан, сразу выдаем триал
        await call.answer("Проверка пройдена! Активируем пробный период...", show_alert=True)
        await call.message.delete()
        await give_trial_subscription(user_id, bot, xui, call.message.chat.id)
    else:
        # Если не подписан, показываем каналы
        channels = await db.get_all_required_channels()
        if not channels:
            logger.warning(f"User {user_id} is starting trial, but no channels are in DB. Giving trial immediately.")
            await call.answer("Активируем пробный период...", show_alert=True)
            await call.message.delete()
            await give_trial_subscription(user_id, bot, xui, call.message.chat.id)
            return

        keyboard = channels_subscribe_keyboard(channels)
        await call.message.edit_text(
            "❗️ <b>Для получения пробного периода, пожалуйста, подпишитесь на наши каналы.</b>\n\n"
            "После подписки нажмите кнопку «Проверить» ниже.",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

# --- ХЕНДЛЕР ДЛЯ КНОПКИ ПРОВЕРКИ ---
@start_router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(call: CallbackQuery, bot: Bot, xui: XUIClient):
    user_id = call.from_user.id
    
    user = await db.get_user(user_id)
    if user and user.has_received_trial:
        await call.answer("Вы уже активировали свою подписку.", show_alert=True)
        await call.message.delete()
        await call.message.answer("Воспользуйтесь главным меню.", reply_markup=main_menu_keyboard())
        return

    is_subscribed = await check_subscription(bot, user_id)

    if is_subscribed:
        await call.answer("✅ Отлично! Спасибо за подписку. Активируем пробный период...", show_alert=True)
        await call.message.delete()
        # --- ИЗМЕНЕНИЕ: Убираем bot из вызова ---
        await give_trial_subscription(user_id=user_id, bot=bot, xui=xui, chat_id=call.message.chat.id)
    else:
        await call.answer("Вы еще не подписались на все каналы. Пожалуйста, попробуйте снова.", show_alert=True)
# --- ИЗМЕНЕНИЕ: Получаем XUIClient вместо MarzClientCache ---
async def activate_referral_bonus(message: Message, referrer_id: int, xui: XUIClient, bot: Bot):
    """Вспомогательная функция для активации реферального бонуса."""
    user_id = message.from_user.id
    bonus_days = 3
    # --- ИЗМЕНЕНИЕ: Используем консистентное имя переменной ---
    xui_username = f"user_{user_id}" 
    try:
        # --- ИЗМЕНЕНИЕ: Вызываем метод нашего нового клиента ---
        result = await xui.add_user(username=xui_username, expire_days=bonus_days)

        if not result:
            # Если клиент вернул None, значит создать пользователя не удалось
            raise Exception("XUIClient returned None, user was not created.")

        logger.info(f"Successfully created 3x-ui user '{xui_username}' with {bonus_days} bonus days.")
        
        # Обновляем наши БД
        await db.set_user_referrer(user_id, referrer_id)
        # --- ИЗМЕНЕНИЕ: Обновляем правильное поле в БД ---
        await db.update_user_xui_username(user_id, xui_username)
        await db.extend_user_subscription(user_id, days=bonus_days)
        
        await message.answer(f"🎉 Вы пришли по приглашению и получили <b>пробную подписку на {bonus_days} дня</b>!")
        
        # Уведомляем реферера
        try:
            await bot.send_message(referrer_id, f"По вашей ссылке зарегистрировался новый пользователь: {message.from_user.full_name}!")
        except Exception as e:
            logger.error(f"Could not send notification to referrer {referrer_id}: {e}")
            
    except Exception as e:
        # --- ИЗМЕНЕНИЕ: Обновляем текст лога ---
        logger.error(f"Failed to create 3x-ui user for referral bonus for user {user_id}: {e}", exc_info=True)
        await message.answer("Произошла ошибка при активации вашего стартового бонуса. Пожалуйста, обратитесь в поддержку.")

# =============================================================================
# --- БЛОК: ОТОБРАЖЕНИЕ РЕФЕРАЛЬНОЙ ПРОГРАММЫ (БЕЗ ИЗМЕНЕНИЙ) ---
# Этот блок не взаимодействует с API панели, поэтому его не нужно менять.
# =============================================================================

async def show_referral_info(message: Message, bot: Bot):
    """Вспомогательная функция для показа информации о реферальной программе."""
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    user_data = await db.get_user(user_id)
    referral_count = await db.count_user_referrals(user_id)

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
    
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=back_to_main_menu_keyboard())
    else:
        await message.answer(text, reply_markup=back_to_main_menu_keyboard())

@start_router.message(Command("referral"))
async def referral_command_handler(message: Message, bot: Bot):
    await show_referral_info(message, bot)

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

    try:
        await call.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass
        await call.message.answer(text, reply_markup=reply_markup)