# database/requests.py (Полностью исправленная и отрефакторенная версия)

from db import db, User, Tariff, PromoCode, UsedPromoCode
from peewee import DoesNotExist
from datetime import datetime, timedelta

# --- Декоратор для безопасной работы с БД ---
def db_connection(func):
    """Декоратор для автоматического управления соединением с БД."""
    def wrapper(*args, **kwargs):
        db.connect(reuse_if_open=True)
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            if not db.is_closed():
                db.close()
    return wrapper

# =============================================================================
# --- Функции для работы с пользователями (User) ---
# =============================================================================

@db_connection
def get_or_create_user(user_id: int, full_name: str, username: str | None = None) -> tuple[User, bool]:
    user, created = User.get_or_create(
        user_id=user_id,
        defaults={'full_name': full_name, 'username': username}
    )
    return user, created

@db_connection
def get_user(user_id: int) -> User | None:
    try:
        return User.get(User.user_id == user_id)
    except DoesNotExist:
        return None

@db_connection
def get_user_by_username(username: str) -> User | None:
    try:
        return User.get(User.username.ilike(username))
    except DoesNotExist:
        return None
        
@db_connection
def get_all_users_ids() -> list[int]:
    return [user_id for user_id, in User.select(User.user_id).tuples().iterator()]

@db_connection
def update_user_marzban_username(user_id: int, marzban_username: str):
    query = User.update(marzban_username=marzban_username).where(User.user_id == user_id)
    query.execute()

@db_connection
def extend_user_subscription(user_id: int, days: int):
    user = get_user(user_id)
    if not user:
        return
    
    now = datetime.now()
    if user.subscription_end_date and user.subscription_end_date > now:
        new_date = user.subscription_end_date + timedelta(days=days)
    else:
        new_date = now + timedelta(days=days)
    
    query = User.update(subscription_end_date=new_date).where(User.user_id == user_id)
    query.execute()

@db_connection
def set_user_referrer(user_id: int, referrer_id: int):
    query = User.update(referrer_id=referrer_id).where(User.user_id == user_id)
    query.execute()

@db_connection
def add_bonus_days(user_id: int, days: int):
    user = get_user(user_id)
    if user:
        new_bonus_days = user.referral_bonus_days + days
        query = User.update(referral_bonus_days=new_bonus_days).where(User.user_id == user_id)
        query.execute()

@db_connection
def set_first_payment_done(user_id: int):
    query = User.update(is_first_payment_made=True).where(User.user_id == user_id)
    query.execute()

@db_connection
def delete_user(user_id: int) -> bool:
    try:
        user = User.get(User.user_id == user_id)
        user.delete_instance(recursive=True)
        return True
    except User.DoesNotExist:
        return False

# database/requests.py

@db_connection
def get_users_with_expiring_subscription(days_left: int):
    """
    Возвращает пользователей, у которых подписка истекает
    ровно через `days_left` дней.
    """
    # Вычисляем целевую дату
    target_date_start = datetime.now().date() + timedelta(days=days_left)
    target_date_end = target_date_start + timedelta(days=1)
    
    # Ищем пользователей, у которых дата окончания подписки попадает в этот день
    return User.select().where(
        User.subscription_end_date >= target_date_start,
        User.subscription_end_date < target_date_end
    )
# database/requests.py

@db_connection
def get_users_with_expiring_subscription_in_hours(hours: int):
    """
    Возвращает пользователей, у которых подписка истекает
    в промежутке от 지금 до ближайших X часов.
    """
    now = datetime.now()
    expiration_limit = now + timedelta(hours=hours)
    
    # Ищем пользователей, у которых дата окончания > сейчас И < сейчас + X часов
    return User.select().where(
        User.subscription_end_date > now,
        User.subscription_end_date <= expiration_limit
    )

# =============================================================================
# --- Функции для работы с тарифами (Tariff) ---
# =============================================================================

@db_connection
def get_active_tariffs():
    """Возвращает список всех активных тарифов, отсортированных по цене."""
    # Используем .order_by() для сортировки
    return Tariff.select().where(Tariff.is_active == True).order_by(Tariff.price.asc())

@db_connection
def get_all_tariffs():
    return Tariff.select()

@db_connection
def get_tariff_by_id(tariff_id: int) -> Tariff | None:
    try:
        return Tariff.get(Tariff.id == tariff_id)
    except DoesNotExist:
        return None

@db_connection
def add_new_tariff(name: str, price: float, duration_days: int) -> Tariff:
    return Tariff.create(name=name, price=price, duration_days=duration_days, is_active=True)

@db_connection
def update_tariff_field(tariff_id: int, field: str, value):
    query = Tariff.update({getattr(Tariff, field): value}).where(Tariff.id == tariff_id)
    query.execute()

@db_connection
def delete_tariff_by_id(tariff_id: int):
    query = Tariff.delete().where(Tariff.id == tariff_id)
    query.execute()

# =============================================================================
# --- Функции для сбора статистики ---
# =============================================================================

@db_connection
def count_all_users() -> int:
    return User.select().count()

@db_connection
def count_new_users_for_period(days: int) -> int:
    start_date = datetime.now() - timedelta(days=days)
    return User.select().where(User.reg_date >= start_date).count()

@db_connection
def count_active_subscriptions() -> int:
    return User.select().where(
        User.subscription_end_date.is_null(False) & 
        (User.subscription_end_date > datetime.now())
    ).count()

@db_connection
def count_user_referrals(user_id: int):
    """Считает количество пользователей, приглашенных указанным юзером."""
    return User.select().where(User.referrer_id == user_id).count()

@db_connection
def get_user_referrals(user_id: int):
    """Возвращает список пользователей, приглашенных указанным юзером."""
    return User.select().where(User.referrer_id == user_id)

# =============================================================================
# --- Функции для поддержки ---
# =============================================================================

@db_connection
def set_user_support_topic(user_id: int, topic_id: int):
    query = User.update(support_topic_id=topic_id).where(User.user_id == user_id)
    query.execute()

@db_connection
def clear_user_support_topic(user_id: int):
    query = User.update(support_topic_id=None).where(User.user_id == user_id)
    query.execute()
    
@db_connection
def get_user_by_support_topic(topic_id: int) -> User | None:
    try:
        return User.get(User.support_topic_id == topic_id)
    except DoesNotExist:
        return None

# =============================================================================
# --- Функции для системы промокодов ---
# =============================================================================

@db_connection
def create_promo_code(code, bonus_days=0, discount_percent=0, max_uses=1, expire_date=None):
    return PromoCode.create(
        code=code.upper(),
        bonus_days=bonus_days,
        discount_percent=discount_percent,
        max_uses=max_uses,
        uses_left=max_uses,
        expire_date=expire_date
    )

@db_connection
def get_all_promo_codes():
    return PromoCode.select()

@db_connection
def get_promo_code(code: str) -> PromoCode | None:
    try:
        return PromoCode.get(PromoCode.code == code.upper())
    except DoesNotExist:
        return None

@db_connection
def has_user_used_promo(user_id: int, promo_id: int) -> bool:
    return UsedPromoCode.select().where(
        (UsedPromoCode.user == user_id) &
        (UsedPromoCode.promo_code == promo_id)
    ).exists()

@db_connection
def use_promo_code(user_id: int, promo: PromoCode):
    """Отмечает, что пользователь использовал промокод."""
    with db.atomic(): # Используем транзакцию для безопасности
        promo.uses_left -= 1
        promo.save()
        UsedPromoCode.create(user=user_id, promo_code=promo)

@db_connection
def delete_promo_code(promo_id: int):
    try:
        promo = PromoCode.get_by_id(promo_id)
        promo.delete_instance(recursive=True) # Удалит и все записи об использовании
        return True
    except DoesNotExist:
        return False