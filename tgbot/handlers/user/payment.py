# tgbot/handlers/user/payment.py (Полная, исправленная и оптимизированная версия)

from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command

from loader import logger
from database import requests as db
from marzban.init_client import MarzClientCache
from tgbot.handlers.user.profile import show_profile_logic
from tgbot.keyboards.inline import cancel_fsm_keyboard, tariffs_keyboard, back_to_main_menu_keyboard
from tgbot.services import payment

payment_router = Router()

# --- Состояния FSM ---
class PromoApplyFSM(StatesGroup):
    awaiting_code = State()

# =============================================================================
# --- БЛОК 1: ПОКАЗ ТАРИФОВ ---
# =============================================================================

async def show_tariffs_logic(event: Message | CallbackQuery, state: FSMContext):
    """Универсальная логика для показа списка тарифов."""
    fsm_data = await state.get_data()
    discount = fsm_data.get("discount")
    
    active_tariffs = db.get_active_tariffs()
    tariffs_list = list(active_tariffs) if active_tariffs else []

    text = "Пожалуйста, выберите тарифный план:"
    if discount:
        text = f"✅ Промокод на <b>{discount}%</b> применен!\n\n" + text

    reply_markup = tariffs_keyboard(tariffs_list)

    if not tariffs_list:
        text = "К сожалению, сейчас нет доступных тарифов для покупки."
        reply_markup = back_to_main_menu_keyboard()
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup)
    else:
        await event.answer(text, reply_markup=reply_markup)

@payment_router.message(Command("payment"))
async def payment_command_handler(message: Message, state: FSMContext):
    await show_tariffs_logic(message, state)

@payment_router.callback_query(F.data == "buy_subscription")
async def buy_subscription_callback_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await show_tariffs_logic(call, state)

# =============================================================================
# --- БЛОК 2: ПРИМЕНЕНИЕ ПРОМОКОДА ---
# =============================================================================
async def _start_promo_input(event: Message | CallbackQuery, state: FSMContext):
    """
    Универсальная функция для начала сценария ввода промокода.
    """
    await state.set_state(PromoApplyFSM.awaiting_code)
    
    text = "Введите ваш промокод:"
    # Кнопка "Отмена" будет возвращать пользователя к списку тарифов
    reply_markup = back_to_main_menu_keyboard()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup)
    else: # если это Message
        await event.answer(text, reply_markup=reply_markup)


@payment_router.message(Command("promo"))
async def promo_command_handler(message: Message, state: FSMContext):
    """Начинает сценарий ввода промокода по команде."""
    # Просто вызываем нашу универсальную функцию
    await _start_promo_input(message, state)


# --- ОБНОВЛЕННЫЙ хендлер для кнопки "Ввести промокод" ---
@payment_router.callback_query(F.data == "enter_promo_code")
async def enter_promo_callback_handler(call: CallbackQuery, state: FSMContext):
    """Начинает сценарий ввода промокода по кнопке."""
    await call.answer()
    # Просто вызываем нашу универсальную функцию
    await _start_promo_input(call, state)
        
@payment_router.message(PromoApplyFSM.awaiting_code)
async def process_promo_code(message: Message, state: FSMContext, bot: Bot, marzban: MarzClientCache):
    """Обрабатывает введенный промокод."""
    code = message.text.upper()
    promo = db.get_promo_code(code)
    user_id = message.from_user.id

    await message.delete() # Сразу удаляем сообщение с кодом

    error_text = None
    if not promo: error_text = "Промокод не найден."
    elif promo.uses_left <= 0: error_text = "Этот промокод уже закончился."
    elif promo.expire_date and promo.expire_date < datetime.now(): error_text = "Срок действия этого промокода истек."
    elif db.has_user_used_promo(user_id, promo.id): error_text = "Вы уже использовали этот промокод."

    if error_text:
        await message.answer(error_text)
        return

    db.use_promo_code(user_id, promo)

    if promo.bonus_days > 0:
        await state.clear()
        user_from_db = db.get_user(user_id) # Получаем юзера один раз
        marzban_username = (user_from_db.marzban_username or f"user_{user_id}").lower()
        
        try:
            # --- ИСПРАВЛЕНО: Используем наш "умный" метод modify_user ---
            await marzban.modify_user(username=marzban_username, expire_days=promo.bonus_days)
            
            # Обновляем наши локальные данные ТОЛЬКО после успешной операции в Marzban
            db.extend_user_subscription(user_id, promo.bonus_days)
            if not user_from_db.marzban_username:
                db.update_user_marzban_username(user_id, marzban_username)
            
            await message.answer(f"✅ Промокод успешно применен! Вам начислено <b>{promo.bonus_days} бонусных дней</b>.")
            # Показываем обновленный профиль
            await show_profile_logic(message, marzban, bot)

        except Exception as e:
            logger.error(f"Failed to apply bonus days for promo code {code} for user {user_id}: {e}", exc_info=True)
            await message.answer("❌ Произошла ошибка при начислении бонусных дней. Обратитесь в поддержку.")
    
    elif promo.discount_percent > 0:
        # Сохраняем скидку в состояние и показываем тарифы
        await state.set_state(None) # Выходим из состояния ввода промокода
        await state.update_data(discount=promo.discount_percent, promo_code=code)
        await show_tariffs_logic(message, state)

# =============================================================================
# --- БЛОК 3: ВЫБОР ТАРИФА И СОЗДАНИЕ ПЛАТЕЖА ---
# =============================================================================

@payment_router.callback_query(F.data.startswith("select_tariff_"))
async def select_tariff_handler(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Обрабатывает выбор тарифа и генерирует ссылку на оплату."""
    await call.answer()
    
    tariff_id = int(call.data.split("_")[2])
    tariff = db.get_tariff_by_id(tariff_id)
    if not tariff:
        await call.message.edit_text("Ошибка! Тариф не найден.", reply_markup=back_to_main_menu_keyboard())
        return

    fsm_data = await state.get_data()
    discount_percent = fsm_data.get("discount")
    promo_code = fsm_data.get("promo_code")

    original_price = tariff.price
    final_price = original_price
    
    if discount_percent:
        final_price = round(original_price * (1 - discount_percent / 100), 2)
        price_text = (
            f"<s>{original_price} RUB</s>\n"
            f"Скидка {discount_percent}% ({promo_code}): <b>{final_price} RUB</b>"
        )
    else:
        price_text = f"<b>{original_price} RUB</b>"

    payment_url, _ = payment.create_payment(
        user_id=call.from_user.id,
        amount=final_price,
        description=f"Оплата тарифа '{tariff.name}'" + (f" (скидка {discount_percent}%)" if discount_percent else ""),
        bot_username=(await bot.get_me()).username,
        metadata={'user_id': str(call.from_user.id), 'tariff_id': tariff_id}
    )

    payment_kb = InlineKeyboardBuilder()
    payment_kb.button(text="💳 Перейти к оплате", url=payment_url)
    payment_kb.button(text="⬅️ Назад к выбору тарифа", callback_data="buy_subscription")
    payment_kb.adjust(1)
    
    sent_message = await call.message.edit_text(
        f"Вы выбрали тариф: <b>{tariff.name}</b>\n"
        f"Срок: <b>{tariff.duration_days} дней</b>\n\n"
        f"Сумма к оплате: {price_text}\n\n"
        "Нажмите на кнопку ниже, чтобы перейти к оплате.",
        reply_markup=payment_kb.as_markup()
    )
    await state.update_data(payment_message_id=sent_message.message_id)