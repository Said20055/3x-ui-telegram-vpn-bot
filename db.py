# db.py (ФИНАЛЬНАЯ ВЕРСИЯ НА SQLAlchemy)

import datetime
from sqlalchemy import (
    create_engine, BigInteger, String, DateTime, Boolean, ForeignKey,
    Integer, Float, select, func
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import load_config

# --- 1. Настройка ---
config = load_config()
db_config = config.dataBase
DSN = f"postgresql+asyncpg://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.db_name}"
SYNC_DSN = f"postgresql://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.db_name}"

# Создаем асинхронный "движок" и фабрику сессий
async_engine = create_async_engine(DSN)
async_session_maker = async_sessionmaker(async_engine, expire_on_commit=False)

# --- 2. Базовая модель ---
class Base(DeclarativeBase):
    pass

# --- 3. Определяем все ваши модели на новом синтаксисе ---
class User(Base):
    __tablename__ = 'users'
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String)
    reg_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    subscription_end_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    xui_username: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    
    # --- НОВОЕ ПОЛЕ ДЛЯ ОТСЛЕЖИВАНИЯ ТРИАЛА ---
    has_received_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    referral_bonus_days: Mapped[int] = mapped_column(Integer, default=0)
    is_first_payment_made: Mapped[bool] = mapped_column(Boolean, default=False)
    support_topic_id: Mapped[int] = mapped_column(Integer, nullable=True)

class Tariff(Base):
    __tablename__ = 'tariffs'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float)
    duration_days: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class PromoCode(Base):
    __tablename__ = 'promo_codes'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    bonus_days: Mapped[int] = mapped_column(Integer, default=0)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    expire_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    uses_left: Mapped[int] = mapped_column(Integer, default=1)

class UsedPromoCode(Base):
    __tablename__ = 'used_promo_codes'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id'))
    promo_code_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('promo_codes.id'))
    used_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

class RequiredChannel(Base):
    __tablename__ = 'required_channels'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    channel_name: Mapped[str] = mapped_column(String)
    channel_url: Mapped[str] = mapped_column(String)


# --- 4. Функция для создания таблиц ---
def setup_database_sync():
    """Создает таблицы синхронно при старте бота."""
    engine = create_engine(SYNC_DSN)
    Base.metadata.create_all(engine)
    print("INFO: Database tables created or already exist via SQLAlchemy.")