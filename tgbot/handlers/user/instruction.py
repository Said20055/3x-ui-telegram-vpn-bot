# tgbot/handlers/user/instruction.py

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем клавиатуру для кнопки "Назад"
from tgbot.keyboards.inline import back_to_main_menu_keyboard

# Создаем новый роутер специально для инструкций
instruction_router = Router(name="instruction")


# --- 1. Клавиатура со ссылками на клиенты ---
def os_client_keyboard():
    """
    Создает клавиатуру со ссылками на рекомендованные клиенты для VLESS.
    """
    builder = InlineKeyboardBuilder()
    # Windows: NekoBox - мощный и универсальный клиент
    builder.button(text="💻 Windows (NekoBox) Скачается Zip-архив", url="https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-windows64.zip")
    # Android: v2rayNG - самый популярный и стабильный
    builder.button(text="🤖 Android (V2RayTun)", url="https://play.google.com/store/apps/details?id=com.v2raytun.android&pcampaignid=web_share")
    # iOS/iPadOS: Foxtrot или Streisand - оба отличные
    builder.button(text="🍏 iOS (V2RayTun)", url="https://apps.apple.com/ru/app/v2raytun/id6476628951")
    
    # macOS: V2rayU - хороший выбор для Mac
    builder.button(text="🍎 macOS (V2rayU)", url="https://github.com/yanue/V2rayU/releases/latest")
    # Добавляем кнопку "Назад"
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    # Располагаем кнопки по одной в ряд для лучшей читаемости
    builder.adjust(1)
    return builder.as_markup()


# --- 2. Универсальная функция для показа инструкции ---
async def show_instruction_message(event: types.Message | types.CallbackQuery):
    """
    Показывает пользователю инструкцию по подключению.
    """
    text = (
        "📲 <b>Инструкция по подключению (VLESS)</b>\n\n"
        "1️⃣ <b>Скопируйте ссылку</b>\n"
        "В разделе «👤 Мой профиль» нажмите на вашу ссылку подписки, чтобы скопировать её.\n\n"
        "2️⃣ <b>Установите приложение</b>\n"
        "Выберите вашу операционную систему ниже и установите рекомендованное приложение.\n\n"
        "3️⃣ <b>Добавьте подписку</b>\n"
        "В приложении найдите раздел «Подписки» (Subscriptions), нажмите 'Добавить' (+) и вставьте скопированную ссылку.\n\n"
        "4️⃣ <b>Подключитесь</b>\n"
        "После добавления обновите список серверов, выберите любой из них и нажмите кнопку подключения."
    )
    reply_markup = os_client_keyboard()

    # Отправляем или редактируем сообщение
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup)
    else:
        await event.answer(text, reply_markup=reply_markup)


# --- 3. Хендлеры для команды и кнопки ---

# Хендлер для команды /instruction
@instruction_router.message(Command("instruction"))
async def instruction_command_handler(message: types.Message):
    await show_instruction_message(message)

# Хендлер для кнопки "Инструкция" из главного меню
# (callback_data должен быть "instruction_info")
@instruction_router.callback_query(F.data == "instruction_info")
async def instruction_callback_handler(call: types.CallbackQuery):
    await call.answer()
    await show_instruction_message(call)