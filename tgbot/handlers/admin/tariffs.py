from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from loader import logger

from tgbot.filters.admin import IsAdmin
from database import requests as db
from tgbot.keyboards.inline import (tariffs_list_keyboard, single_tariff_manage_keyboard, 
                                    confirm_delete_tariff_keyboard, cancel_fsm_keyboard)

admin_tariffs_router = Router()
admin_tariffs_router.message.filter(IsAdmin())
admin_tariffs_router.callback_query.filter(IsAdmin())


# --- Состояния FSM для добавления/редактирования тарифа ---
class TariffFSM(StatesGroup):
    add_name = State()
    add_price = State()
    add_duration = State()
    edit_field = State()


# --- Хелпер для показа карточки тарифа ---
async def show_tariff_card(call: CallbackQuery, tariff_id: int):
    tariff = await db.get_tariff_by_id(tariff_id)
    if not tariff:
        await call.message.edit_text("Тариф не найден.")
        return
    
    status = "Активен ✅" if tariff.is_active else "Отключен ❌"
    text = (
        f"<b>Управление тарифом:</b> «{tariff.name}»\n\n"
        f"<b>ID:</b> <code>{tariff.id}</code>\n"
        f"<b>Цена:</b> {tariff.price} RUB\n"
        f"<b>Срок:</b> {tariff.duration_days} дн.\n"
        f"<b>Статус:</b> {status}"
    )
    await call.message.edit_text(text, reply_markup=single_tariff_manage_keyboard(tariff.id, tariff.is_active))


# --- Основное меню управления тарифами ---
@admin_tariffs_router.callback_query(F.data == "admin_tariffs_menu")
async def tariffs_menu(call: CallbackQuery):
    tariffs = await db.get_all_tariffs()
    await call.message.edit_text(
        "<b>💳 Управление тарифами</b>\n\nВыберите тариф для редактирования или добавьте новый.",
        reply_markup=tariffs_list_keyboard(list(tariffs))
    )

# --- Показ карточки конкретного тарифа ---
@admin_tariffs_router.callback_query(F.data.startswith("admin_manage_tariff_"))
async def manage_single_tariff(call: CallbackQuery):
    tariff_id = int(call.data.split("_")[3])
    await show_tariff_card(call, tariff_id)


# --- Включение / Отключение тарифа ---
@admin_tariffs_router.callback_query(F.data.startswith("admin_toggle_tariff_"))
async def toggle_tariff_status(call: CallbackQuery):
    tariff_id = int(call.data.split("_")[3])
    tariff = await db.get_tariff_by_id(tariff_id)
    if tariff:
        new_status = not tariff.is_active
        await db.update_tariff_field(tariff_id, 'is_active', new_status)
        await call.answer(f"Статус изменен на {'Активен' if new_status else 'Отключен'}")
        await show_tariff_card(call, tariff_id)


# --- Блок удаления тарифа ---
@admin_tariffs_router.callback_query(F.data.startswith("admin_delete_tariff_"))
async def delete_tariff_confirm(call: CallbackQuery):
    tariff_id = int(call.data.split("_")[3])
    await call.message.edit_text(
        "Вы уверены, что хотите удалить этот тариф? Это действие необратимо.",
        reply_markup=confirm_delete_tariff_keyboard(tariff_id)
    )

@admin_tariffs_router.callback_query(F.data.startswith("admin_confirm_delete_tariff_"))
async def delete_tariff_finish(call: CallbackQuery):
    tariff_id = int(call.data.split("_")[4])
    await db.delete_tariff_by_id(tariff_id)
    await call.answer("Тариф успешно удален", show_alert=True)
    await tariffs_menu(call) # Возвращаемся к списку тарифов


# --- Блок добавления нового тарифа (FSM) ---
@admin_tariffs_router.callback_query(F.data == "admin_add_tariff")
async def add_tariff_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(TariffFSM.add_name)
    await call.message.edit_text("<b>Шаг 1/3:</b> Введите название нового тарифа (например, 'Промо-тариф на неделю').", 
                                reply_markup=cancel_fsm_keyboard("admin_tariffs_menu"))

@admin_tariffs_router.message(TariffFSM.add_name)
async def add_tariff_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(TariffFSM.add_price)
    await message.answer("<b>Шаг 2/3:</b> Теперь введите цену тарифа в рублях (например, 99 или 99.9).")

@admin_tariffs_router.message(TariffFSM.add_price)
async def add_tariff_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Ошибка. Введите корректное число для цены.")
        return
    await state.update_data(price=price)
    await state.set_state(TariffFSM.add_duration)
    await message.answer("<b>Шаг 3/3:</b> Введите срок действия тарифа в днях (например, 7 или 30).")

@admin_tariffs_router.message(TariffFSM.add_duration)
async def add_tariff_duration(message: Message, state: FSMContext):
    try:
        duration = int(message.text)
    except ValueError:
        await message.answer("Ошибка. Введите целое число для количества дней.")
        return
    
    data = await state.get_data()
    new_tariff = await db.add_new_tariff(
        name=data['name'],
        price=data['price'],
        duration_days=duration
    )
    await state.clear()
    await message.answer(f"✅ Новый тариф «{new_tariff.name}» успешно создан!")
    


# --- Блок редактирования существующего тарифа (FSM) ---
# Общий хендлер для входа в режим редактирования
@admin_tariffs_router.callback_query(F.data.startswith("admin_edit_tariff_"))
async def edit_tariff_start(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    field_to_edit = parts[3]
    tariff_id = int(parts[4])
    
    field_map = {
        "name": "название",
        "price": "цену (число)",
        "duration": "срок в днях (целое число)"
    }
    prompt_text = f"Введите новое {field_map[field_to_edit]} для тарифа <code>{tariff_id}</code>"
    
    await state.set_state(TariffFSM.edit_field)
    await state.update_data(tariff_id=tariff_id, field_to_edit=field_to_edit)
    await call.message.edit_text(prompt_text, reply_markup=cancel_fsm_keyboard(f"admin_manage_tariff_{tariff_id}"))

@admin_tariffs_router.message(TariffFSM.edit_field)
async def edit_tariff_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    tariff_id = data['tariff_id']
    field = data['field_to_edit']
    new_value = message.text

    # Валидация
    try:
        if field == 'price':
            new_value = float(new_value.replace(",", "."))
        elif field == 'duration':
            new_value = int(new_value)
    except ValueError:
        await message.answer("Неверный формат данных. Попробуйте еще раз.")
        return

    await db.update_tariff_field(tariff_id, field, new_value)
    await state.clear()
    await message.answer("✅ Данные тарифа успешно обновлены!")