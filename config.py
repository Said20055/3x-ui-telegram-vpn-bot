from dataclasses import dataclass

from environs import Env


@dataclass
class TgBot:
    token: str
    admin_ids: list[int]
    support_chat_id: int
    transaction_log_topic_id: int

    @staticmethod
    def from_env(env: Env):
        token = env.str("BOT_TOKEN")
        # env.list преобразует строку "123,456" в список [123, 456]
        admin_ids = env.list("ADMINS", subcast=int)
        support_chat_id = env.int("SUPPORT_CHAT_ID")
        transaction_log_topic_id = env.int("TRANSACTION_LOG_TOPIC_ID")
        return TgBot(token=token, admin_ids=admin_ids,
                     support_chat_id=support_chat_id,
                     transaction_log_topic_id=transaction_log_topic_id)
@dataclass
class YooKassa:
    shop_id: str
    secret_key: str

    @staticmethod
    def from_env(env: Env):
        shop_id = env.str("YOOKASSA_SHOP_ID")
        secret_key = env.str("YOOKASSA_SECRET_KEY")
        return YooKassa(shop_id=shop_id, secret_key=secret_key)
@dataclass
class DataBase:
    host: str
    port: str
    user: str
    password: str
    db_name: str

    @staticmethod
    def from_env(env: Env):
        host = env.str("DB_HOST")
        port = env.str("DB_PORT")
        user = env.str("DB_USER")
        password = env.str("DB_PASSWORD")
        db_name = env.str("DB_NAME")
        return DataBase(host=host, port=port, user=user, password=password, db_name=db_name)


@dataclass
class Webhook:
    url: str
    domain: str
    use_webhook: bool

    @staticmethod
    def from_env(env: Env):
        url = env.str('SERVER_URL')
        domain = env.str('DOMAIN')
        use_webhook = env.bool('USE_WEBHOOK')
        return Webhook(url=url, domain=domain, use_webhook=use_webhook)


@dataclass
class Xui:
  
    host: str
    username: str
    password: str
    inbound_id: int
    verify_ssl: bool

    @staticmethod
    def from_env(env: Env):
        """
        Создает экземпляр конфигурации Xui из переменных окружения.
        """
        # Мы больше не используем отдельный env_marz, 
        # все переменные для XUI будут с префиксом XUI_
        host = env.str("XUI_HOST")
        username = env.str("XUI_USERNAME") 
        password = env.str("XUI_PASSWORD") 
        inbound_id = env.int("XUI_INBOUND_ID")
        # По умолчанию SSL не проверяем, т.к. бот и панель в одной Docker-сети.
        # Пользователь может переопределить это, если бот будет работать вне Docker.
        verify_ssl = env.bool("XUI_VERIFY_SSL", False) 

        return Xui(
            host=host,
            username=username,
            password=password,
            inbound_id=inbound_id,
            verify_ssl=verify_ssl
        )



@dataclass
class Config:
    tg_bot: TgBot
    webhook: Webhook
    xui: Xui
    dataBase: DataBase
    yookassa: YooKassa


def load_config():
    env = Env()
    env.read_env('.env')
    env_3xui = Env()
    env_3xui.read_env('.env.3xui')
    return Config(
        tg_bot=TgBot.from_env(env),
        webhook=Webhook.from_env(env),
        xui=Xui.from_env(env_3xui),
        dataBase=DataBase.from_env(env),
        yookassa=YooKassa.from_env(env)
    )
