
import uuid
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification


# Импортируем наш объект конфига из loader
from loader import config

# Настраиваем SDK YooKassa
Configuration.account_id = config.yookassa.shop_id
Configuration.secret_key = config.yookassa.secret_key


def create_payment(user_id: int, amount: int, description: str, bot_username: str, metadata: dict = None):
    """
    Создает платеж в YooKassa и возвращает ссылку на оплату.
    """
    # Создаем уникальный ключ идемпотентности для каждого платежа
    idempotence_key = str(uuid.uuid4())
    
    receipt_data = {
        "customer": {
            # ЮKassa требует хотя бы один контакт: email или телефон.
            # Так как мы не знаем email пользователя, можно использовать "заглушку"
            # или предоставить ваш контактный email для всех чеков.
            # ВАЖНО: Уточните у поддержки ЮKassa, какой email лучше указывать.
            "email": f"user_{user_id}@yourdomain.com" 
        },
        "items": [
            {
                "description": description, # Описание товара/услуги
                "quantity": "1.00",         # Количество
                "amount": {
                    "value": f"{amount:.2f}", # Цена за единицу (с двумя знаками после запятой)
                    "currency": "RUB"
                },
                "vat_code": "1", # "НДС не облагается". Если у вас другая система, измените. (1-без ндс, 2-0%, 3-10%, 4-20%)
                "payment_mode": "full_prepayment", # Признак способа расчета - 100% предоплата
                "payment_subject": "service"       # Признак предмета расчета - "Услуга"
            }
        ]
    }
    
    payment = Payment.create({
        "amount": {
            "value": str(amount),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            # Ссылка, куда вернется пользователь после оплаты
            "return_url": f"https://t.me/{bot_username}" 
        },
        "capture": True,
        "description": description,
        "metadata": metadata or {'user_id': str(user_id)},
        "receipt": receipt_data
    }, idempotence_key)
    
    # Возвращаем URL для оплаты и ID платежа
    return payment.confirmation.confirmation_url, payment.id


def parse_webhook_notification(request_body: dict) -> WebhookNotification | None:
    """
    Парсит тело запроса от YooKassa, чтобы убедиться, что это валидное уведомление.
    """
    try:
        notification_object = WebhookNotification(request_body)
        return notification_object
    except Exception:
        # Если тело запроса невалидно, вернется None
        return None