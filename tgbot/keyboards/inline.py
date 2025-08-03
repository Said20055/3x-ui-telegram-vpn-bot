# tgbot/keyboards/inline.py (чистая, финальная версия)

from aiogram.utils.keyboard import InlineKeyboardBuilder
from db import Tariff, PromoCode  # Корректный импорт для вашей структуры
from loader import logger
from urllib.parse import quote_plus


def main_menu_keyboard():
    """Главная клавиатура, которая будет показываться пользователю в основном меню."""
    builder = InlineKeyboardBuilder()
    builder.button(text='💎 Продлить / Оплатить', callback_data='buy_subscription')
    builder.button(text='👤 Мой профиль', callback_data='my_profile')
    builder.button(text='🔑 Мои ключи', callback_data='my_keys')
    builder.button(text='🤝 Реферальная программа', callback_data='referral_program')
    builder.button(text="📲 Инструкция по подключению", callback_data="instruction_info")
    builder.button(text="🎁 Ввести промокод", callback_data="enter_promo_code")
    builder.button(text="💬 Поддержка", callback_data="support_chat_start")
    
    # Расставляем кнопки: 1, 2, 2. Выглядит аккуратно.
    builder.adjust(1, 2, 2)
    return builder.as_markup()


def tariffs_keyboard(tariffs: list[Tariff]):
    """Создает клавиатуру со списком тарифов."""
    builder = InlineKeyboardBuilder()
    for tariff in tariffs:
        # В callback_data передаем ID тарифа
        builder.button(
            text=f"{tariff.name} - {tariff.price} RUB",
            callback_data=f"select_tariff_{tariff.id}"
        )
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.adjust(1) # Каждый тариф на новой строке для лучшей читаемости
    return builder.as_markup()


def profile_keyboard(subscription_url: str):
    """Клавиатура для раздела "Мой профиль"."""
    REDIRECT_PAGE_URL = "https://vac-service.ru:8443/import"
    
    encoded_url = quote_plus(subscription_url)
    
    # 3. Формируем deep-link
    deep_link = f"v2raytun://import/{encoded_url}"

    # Теперь нужно этот deep-link передать на страницу редиректа
    # Кодируем сам deep-link, чтобы передать его одним параметром
    final_redirect_url = f"{REDIRECT_PAGE_URL}?deeplink={quote_plus(deep_link)}"

    builder = InlineKeyboardBuilder()
    # Теперь URL ведет на безопасный https://, и Telegram его пропустит
    builder.button(text="📲 Импортировать в V2RayTun", url=final_redirect_url)
    builder.button(text="🔄 Обновить", callback_data="my_profile")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()
    

def help_keyboard():
    """Клавиатура для раздела "Помощь" со ссылкой на инструкции."""
    builder = InlineKeyboardBuilder()
    builder.button(text='Клиенты для подключения', url='https://marzban-docs.sm1ky.com/start/reality_app/')
    builder.button(text='⬅️ Назад в главное меню', callback_data='back_to_main_menu')
    builder.adjust(1)
    return builder.as_markup()

def back_to_main_menu_keyboard():
    """Простая клавиатура с одной кнопкой "Назад в главное меню"."""
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Назад в главное меню', callback_data='back_to_main_menu')
    return builder.as_markup()

def back_to_admin_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Назад в главное меню', callback_data='admin_main_menu')
    return builder.as_markup()

def admin_main_menu_keyboard():
    """Главное меню админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Управление пользователями", callback_data="admin_users_menu")
    builder.button(text="📈 Статистика", callback_data="admin_stats")
    builder.button(text="💳 Управление тарифами", callback_data="admin_tariffs_menu")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🎁 Промокоды", callback_data="admin_promo_codes")
    builder.adjust(1)
    return builder.as_markup()

def user_manage_keyboard(user_id: int):
    """Клавиатура для управления конкретным пользователем."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Добавить дни", callback_data=f"admin_add_days_{user_id}")
    builder.button(text="🔄 Сбросить ключ", callback_data=f"admin_reset_user_{user_id}")
    builder.button(text="🗑 Удалить пользователя", callback_data=f"admin_delete_user_{user_id}")
    builder.button(text="⬅️ Назад к поиску", callback_data="admin_users_menu")
    builder.adjust(1)
    return builder.as_markup()

def confirm_delete_keyboard(user_id_to_delete: int):
    """
    Клавиатура для подтверждения удаления пользователя.
    Предлагает два варианта: подтвердить или отменить.
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка для окончательного удаления. В callback_data передаем ID юзера.
    builder.button(text="✅ Да, удалить", callback_data=f"admin_confirm_delete_user_{user_id_to_delete}")
    
    # Кнопка для отмены. Возвращает админа к карточке этого же пользователя.
    builder.button(
        text="❌ Отмена", 
        callback_data=f"admin_show_user_{user_id_to_delete}"
    )
    
    builder.adjust(1) # Располагаем кнопки друг под другом для наглядности
    return builder.as_markup()

def cancel_fsm_keyboard(back_callback_data: str):
    """
    Универсальная клавиатура для отмены любого состояния FSM.
    Принимает callback_data для кнопки "Назад".
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=back_callback_data)
    return builder.as_markup()

def confirm_broadcast_keyboard():
    """Клавиатура для подтверждения рассылки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Начать рассылку", callback_data="broadcast_start")
    builder.button(text="❌ Отмена", callback_data="admin_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def tariffs_list_keyboard(tariffs):
    """Показывает список всех тарифов с кнопкой "Добавить новый"."""
    builder = InlineKeyboardBuilder()
    for tariff in tariffs:
        status_icon = "✅" if tariff.is_active else "❌"
        builder.button(
            text=f"{status_icon} {tariff.name} - {tariff.price} RUB",
            callback_data=f"admin_manage_tariff_{tariff.id}"
        )
    builder.button(text="➕ Добавить новый тариф", callback_data="admin_add_tariff")
    builder.button(text="⬅️ Назад в админ-меню", callback_data="admin_main_menu")
    builder.adjust(1)
    return builder.as_markup()


def single_tariff_manage_keyboard(tariff_id: int, is_active: bool):
    """Клавиатура для управления одним тарифом."""
    builder = InlineKeyboardBuilder()
    
    # Кнопки для редактирования полей
    builder.button(text="✏️ Изменить название", callback_data=f"admin_edit_tariff_name_{tariff_id}")
    builder.button(text="💰 Изменить цену", callback_data=f"admin_edit_tariff_price_{tariff_id}")
    builder.button(text="⏳ Изменить срок (дни)", callback_data=f"admin_edit_tariff_duration_{tariff_id}")
    
    # Кнопка для вкл/выкл
    if is_active:
        builder.button(text="❌ Отключить", callback_data=f"admin_toggle_tariff_{tariff_id}")
    else:
        builder.button(text="✅ Включить", callback_data=f"admin_toggle_tariff_{tariff_id}")
        
    builder.button(text="🗑️ Удалить тариф", callback_data=f"admin_delete_tariff_{tariff_id}")
    builder.button(text="⬅️ Назад к списку тарифов", callback_data="admin_tariffs_menu")
    builder.adjust(1)
    return builder.as_markup()

def confirm_delete_tariff_keyboard(tariff_id: int):
    """Клавиатура для подтверждения удаления тарифа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"admin_confirm_delete_tariff_{tariff_id}")
    builder.button(text="❌ Нет, отмена", callback_data=f"admin_manage_tariff_{tariff_id}")
    builder.adjust(1)
    return builder.as_markup()

def close_support_chat_keyboard():
    """Клавиатура для закрытия чата с поддержкой."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Завершить диалог", callback_data="support_chat_close")
    return builder.as_markup()



def promo_codes_list_keyboard(promo_codes: list[PromoCode]):
    """Показывает список всех промокодов с кнопкой 'Удалить' и 'Добавить'."""
    builder = InlineKeyboardBuilder()
    if promo_codes:
        for code in promo_codes:
            # Формируем текст для кнопки
            info = []
            if code.bonus_days > 0:
                info.append(f"{code.bonus_days} дн.")
            if code.discount_percent > 0:
                info.append(f"{code.discount_percent}%")
            info.append(f"{code.uses_left}/{code.max_uses} исп.")
            
            # Добавляем кнопку для каждого кода
            builder.button(
                text=f"🗑️ {code.code} ({', '.join(info)})",
                callback_data=f"admin_delete_promo_{code.id}"
            )
    
    builder.button(text="➕ Добавить новый промокод", callback_data="admin_add_promo")
    builder.button(text="⬅️ Назад в админ-меню", callback_data="admin_main_menu")
    builder.adjust(1) # Все кнопки по одной в ряд
    return builder.as_markup()


def promo_type_keyboard():
    """Предлагает выбрать тип создаваемого промокода."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 Бонусные дни", callback_data="promo_type_days")
    builder.button(text="💰 Скидка (%)", callback_data="promo_type_discount")
    builder.adjust(1)
    return builder.as_markup()

def back_to_promo_list_keyboard():
    """Клавиатура для возврата к списку промокодов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К списку промокодов", callback_data="admin_promo_codes")
    return builder.as_markup()