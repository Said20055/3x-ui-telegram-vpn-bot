# tgbot/handlers/admin/channels.py
from aiogram import Router, F, Bot, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from tgbot.filters.admin import IsAdmin
from tgbot.keyboards.inline import back_to_admin_main_menu_keyboard # Добавьте/адаптируйте клавиатуры
from database import requests as db

admin_channels_router = Router()
admin_channels_router.message.filter(IsAdmin())
admin_channels_router.callback_query.filter(IsAdmin())

class AdminChannelsFSM(StatesGroup):
    add_channel_id = State()
    delete_channel_id = State()

# --- Главное меню управления каналами ---
@admin_channels_router.callback_query(F.data == "admin_channels_menu")
async def channels_menu(call: CallbackQuery):
    channels = await db.get_all_required_channels()
    text = "<b>📢 Управление обязательной подпиской</b>\n\nТекущие каналы:\n"
    if not channels:
        text += "<i>Список пуст.</i>"
    else:
        for ch in channels:
            text += f"• <code>{ch.channel_id}</code> - <a href='{ch.channel_url}'>{ch.channel_name}</a>\n"
    
    # --- Создайте эту клавиатуру в keyboards/inline.py ---
    from tgbot.keyboards.inline import manage_channels_keyboard
    await call.message.edit_text(text, reply_markup=manage_channels_keyboard(), disable_web_page_preview=True)

# --- Добавление канала ---
@admin_channels_router.callback_query(F.data == "admin_add_channel")
async def add_channel_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "<b>Добавление канала</b>\n\n"
        "1. Добавьте бота в администраторы нужного канала.\n"
        "2. Перешлите сюда любой пост из этого канала."
    )
    await state.set_state(AdminChannelsFSM.add_channel_id)

@admin_channels_router.message(AdminChannelsFSM.add_channel_id, F.forward_from_chat)
async def add_channel_finish(message: Message, state: FSMContext, bot: Bot):
    chat = message.forward_from_chat
    try:
        # Пытаемся создать приватную ссылку на канал
        invite_link = await bot.create_chat_invite_link(chat.id)
        
        await db.add_required_channel(
            channel_id=chat.id,
            channel_name=chat.title,
            channel_url=invite_link.invite_link
        )
        await message.answer(f"✅ Канал «{chat.title}» (<code>{chat.id}</code>) успешно добавлен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении канала: {e}\n\n"
                             "Убедитесь, что бот является администратором канала с правом создания пригласительных ссылок.")
    
    await state.clear()
    # Возвращаемся в меню
    await channels_menu(message) # Нужна адаптация под message

# --- Удаление канала ---
@admin_channels_router.callback_query(F.data == "admin_delete_channel")
async def delete_channel_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("<b>Удаление канала</b>\n\nВведите ID канала для удаления:")
    await state.set_state(AdminChannelsFSM.delete_channel_id)

@admin_channels_router.message(AdminChannelsFSM.delete_channel_id)
async def delete_channel_finish(message: Message, state: FSMContext):
    try:
        channel_id = int(message.text)
        success = await db.delete_required_channel(channel_id)
        if success:
            await message.answer(f"✅ Канал <code>{channel_id}</code> удален.")
        else:
            await message.answer(f"⚠️ Канал <code>{channel_id}</code> не найден в базе.")
    except (ValueError, TypeError):
        await message.answer("❌ Введите корректный ID канала (число).")

    await state.clear()
    # Возвращаемся в меню
    await channels_menu(message) # Нужна адаптация под message