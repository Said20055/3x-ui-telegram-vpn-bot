# tgbot/handlers/admin/main.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from tgbot.filters.admin import IsAdmin
from tgbot.keyboards.inline import admin_main_menu_keyboard
from database import requests as db 
from aiogram.utils.keyboard import InlineKeyboardBuilder

admin_main_router = Router()
admin_main_router.message.filter(IsAdmin()) # Применяем фильтр ко всем хендлерам в этом роутере

@admin_main_router.message(Command("admin"))
async def admin_start(message: Message):
    await message.answer("Добро пожаловать в админ-панель!", reply_markup=admin_main_menu_keyboard())

@admin_main_router.callback_query(F.data == "admin_main_menu")
async def admin_main_menu(call: CallbackQuery):
    await call.message.edit_text("Добро пожаловать в админ-панель!", reply_markup=admin_main_menu_keyboard())

@admin_main_router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(call: CallbackQuery):
    """Показывает статистику бота."""
    # Используем call.answer(), чтобы убрать "часики" на кнопке
    await call.answer("Собираю статистику...")
    
    # Собираем данные с помощью новых функций
    total_users = db.count_all_users()
    active_subs = db.count_active_subscriptions()
    users_today = db.count_new_users_for_period(days=1)
    users_week = db.count_new_users_for_period(days=7)
    users_month = db.count_new_users_for_period(days=30)
    
    # Формируем текст сообщения
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ Активных подписок: <b>{active_subs}</b>\n\n"
        "<b>Новые пользователи:</b>\n"
        f"• За сегодня: <b>{users_today}</b>\n"
        f"• За неделю: <b>{users_week}</b>\n"
        f"• За месяц: <b>{users_month}</b>"
    )
    
    # Создаем клавиатуру с кнопками "Обновить" и "Назад"
    stats_kb = InlineKeyboardBuilder()
    stats_kb.button(text="🔄 Обновить", callback_data="admin_stats")
    stats_kb.button(text="⬅️ Назад", callback_data="admin_main_menu")
    stats_kb.adjust(1)
    
    # Редактируем сообщение, чтобы показать статистику
    await call.message.edit_text(text, reply_markup=stats_kb.as_markup())