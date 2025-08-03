# tgbot/handlers/user/__init__.py

from aiogram import Router, F
from aiogram.enums import ChatType

from .start import start_router
from .profile import profile_router
from .payment import payment_router
from .instruction import instruction_router
# ... (импорты остальных ваших частей user_router)

# Создаем один большой роутер для всех пользовательских хендлеров
user_router = Router(name="user")

# --- ВОТ ВАЖНОЕ ИЗМЕНЕНИЕ ---
# Применяем фильтр на приватный чат КО ВСЕМ хендлерам ВНУТРИ user_router
user_router.message.filter(F.chat.type == ChatType.PRIVATE)


# Подключаем к нему все дочерние роутеры
user_router.include_routers(
    start_router,
    profile_router,
    payment_router,
    instruction_router
)

__all__ = ["user_router"]