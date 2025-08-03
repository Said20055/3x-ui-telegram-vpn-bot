import logging
import betterlogging as bl
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import load_config  # Убедитесь, что путь до конфига правильный
from marzban.init_client import MarzClientCache
from utils.logger import APINotificationHandler

# Загружаем конфиг
config = load_config()

# loader.py

def setup_logging():
    """Настраивает кастомное логирование с DEBUG уровнем для Aiogram."""
    # Устанавливаем самый подробный уровень
    log_level = logging.DEBUG 
    bl.basic_colorized_config(level=log_level)

    # Устанавливаем базовый конфиг для всех логгеров
    logging.basicConfig(
        level=log_level,
        format="%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s",
    )
    
    # Конкретно для логгера aiogram.event выставляем DEBUG, чтобы видеть все
    logging.getLogger("aiogram.event").setLevel(logging.DEBUG)
    
    logger_init = logging.getLogger(__name__)

    # Отправка критических ошибок админу
    main_admin_id = config.tg_bot.admin_ids[0] if config.tg_bot.admin_ids else None
    if main_admin_id:
        api_handler = APINotificationHandler(config.tg_bot.token, main_admin_id)
        api_handler.setLevel(logging.ERROR)
        logger_init.addHandler(api_handler)

    return logger_init

# --- Инициализируем наши "сервисы" ---

# 1. Логгер
logger = setup_logging()

# 2. Объект бота с вашими настройками
bot = Bot(
    token=config.tg_bot.token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True)
)

# 3. Клиент для Marzban API
# Замечание: URL для клиента лучше формировать без тернарного оператора, 
# так как это может понадобиться в разных частях приложения.
# Если бот работает в Docker, ему нужен внутренний адрес сервиса.
# base_url = f'https://{config.webhook.domain}/' - это внешний адрес для Telegram.
# Убедитесь, что для Marzban используется правильный внутренний или внешний URL.
# Я оставлю ваш вариант, но это место требует внимания.

base_url = f'https://{config.webhook.domain}/' if config.webhook.use_webhook else 'https://free_vpn_bot_marzban:8002'
marzban_client = MarzClientCache(base_url, config, logger)
