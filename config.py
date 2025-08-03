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
class Marzban:
    username: str
    password: str
    token_expire: int
    verify_ssl: bool

    @staticmethod
    def from_env(env: Env, env_marz: Env):
        username = env_marz.str("SUDO_USERNAME")
        password = env_marz.str("SUDO_PASSWORD")
        token_expire = env_marz.int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
        verify_ssl = env.bool("MARZ_HAS_CERTIFICATE")
        return Marzban(username=username, password=password,
                       token_expire=token_expire,
                       verify_ssl=verify_ssl)


@dataclass
class Config:
    tg_bot: TgBot
    webhook: Webhook
    marzban: Marzban
    dataBase: DataBase
    yookassa: YooKassa


def load_config():
    from environs import Env
    env = Env()
    env.read_env('.env')
    env_marz = Env()
    env_marz.read_env('.env.marzban')
    return Config(
        tg_bot=TgBot.from_env(env),
        webhook=Webhook.from_env(env),
        marzban=Marzban.from_env(env, env_marz),
        dataBase=DataBase.from_env(env),
        yookassa=YooKassa.from_env(env)
    )
