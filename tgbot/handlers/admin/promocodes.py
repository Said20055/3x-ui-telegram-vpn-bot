# tgbot/handlers/admin/promocodes.py

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta

from loader import logger
from database import requests as db
from tgbot.keyboards.inline import (promo_codes_list_keyboard, promo_type_keyboard, 
                                    cancel_fsm_keyboard, back_to_promo_list_keyboard) # Нужны новые клавиатуры

admin_promo_router = Router()

class PromoFSM(StatesGroup):
    get_code = State()
    get_type = State()
    get_value = State()
    get_max_uses = State()

async def show_promo_codes_list(event: types.Message | types.CallbackQuery):
    """
    Универсальная функция для отображения списка промокодов.
    Работает и с Message, и с CallbackQuery.
    """
    codes = db.get_all_promo_codes()
    text = "🎁 <b>Управление промокодами</b>"
    reply_markup = promo_codes_list_keyboard(list(codes))
    
    # Отправляем или редактируем сообщение
    if isinstance(event, types.CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=reply_markup)
        except: # Если не вышло, удаляем и шлем новое
            await event.message.delete()
            await event.message.answer(text, reply_markup=reply_markup)
    else: # если это Message
        await event.answer(text, reply_markup=reply_markup)

# --- Главное меню промокодов ---
@admin_promo_router.callback_query(F.data == "admin_promo_codes")
async def promo_codes_menu_callback(call: CallbackQuery):
    """Срабатывает на кнопку 'К списку промокодов'."""
    await call.answer()
    await show_promo_codes_list(call)

# --- Удаление промокода ---
@admin_promo_router.callback_query(F.data.startswith("admin_delete_promo_"))
async def delete_promo(call: CallbackQuery):
    promo_id = int(call.data.split("_")[3])
    db.delete_promo_code(promo_id)
    await call.answer("Промокод удален", show_alert=True)
    await show_promo_codes_list(call)


# --- FSM для создания промокода ---
@admin_promo_router.callback_query(F.data == "admin_add_promo")
async def add_promo_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(PromoFSM.get_code)
    await call.message.edit_text(
        "<b>Шаг 1/4:</b> Введите текст промокода (например, <code>SUMMER2025</code>). Он будет приведен к верхнему регистру.",
        reply_markup=cancel_fsm_keyboard("admin_promo_codes")
    )

@admin_promo_router.message(PromoFSM.get_code)
async def add_promo_code(message: Message, state: FSMContext):
    if db.get_promo_code(message.text):
        await message.answer("Такой промокод уже существует. Введите другой.")
        return
    await state.update_data(code=message.text)
    await state.set_state(PromoFSM.get_type)
    await message.answer("<b>Шаг 2/4:</b> Выберите тип промокода:", reply_markup=promo_type_keyboard())

@admin_promo_router.callback_query(F.data.startswith("promo_type_"), PromoFSM.get_type)
async def add_promo_type(call: CallbackQuery, state: FSMContext):
    promo_type = call.data.split("_")[2]
    await state.update_data(type=promo_type)
    await state.set_state(PromoFSM.get_value)
    
    if promo_type == "days":
        await call.message.edit_text("<b>Шаг 3/4:</b> Введите количество бонусных дней (целое число).")
    elif promo_type == "discount":
        await call.message.edit_text("<b>Шаг 3/4:</b> Введите размер скидки в процентах (целое число от 1 до 99).")

@admin_promo_router.message(PromoFSM.get_value)
async def add_promo_value(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Ошибка. Введите целое число.")
        return
    await state.update_data(value=int(message.text))
    await state.set_state(PromoFSM.get_max_uses)
    await message.answer("<b>Шаг 4/4:</b> Введите максимальное количество использований (целое число).")

@admin_promo_router.message(PromoFSM.get_max_uses)
async def add_promo_max_uses(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Ошибка. Введите целое число.")
        return
    
    data = await state.get_data()
    promo_type = data['type']
    
    db.create_promo_code(
        code=data['code'],
        bonus_days=data['value'] if promo_type == 'days' else 0,
        discount_percent=data['value'] if promo_type == 'discount' else 0,
        max_uses=int(message.text)
    )
    await state.clear()
    await message.answer("✅ Промокод успешно создан!")
    
    # Показываем обновленный список
    fake_call = CallbackQuery(id="fake_call", from_user=message.from_user, chat_instance="", message=message)
    await show_promo_codes_list(fake_call)