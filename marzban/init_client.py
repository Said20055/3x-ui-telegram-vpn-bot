# marzban/init_client.py (оптимизированная версия + метод delete)

import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from marzban_api_client.api.admin import admin_token
from marzban_api_client.models.body_admin_token_api_admin_token_post import (
    BodyAdminTokenApiAdminTokenPost,
)
from marzban_api_client.client import Client

class MarzClientCache:
    def __init__(self, base_url: str, config, logger):
        self._http_client: Optional[httpx.AsyncClient] = None
        self._exp_at: Optional[datetime] = None
        self._base_url: str = base_url
        self._config = config
        self._logger = logger
        self._token: str = ''

    async def _get_token(self) -> str:
        """Получает токен доступа для API Marzban."""
        try:
            login_data = BodyAdminTokenApiAdminTokenPost(
                username=self._config.marzban.username, 
                password=self._config.marzban.password
            )
            async with Client(base_url=self._base_url, verify_ssl=False) as temp_client:
                token_response = await admin_token.asyncio(client=temp_client, body=login_data)
                return token_response.access_token
        except Exception as e:
            self._logger.error(f"Error getting Marzban token: {e}", exc_info=True)
            raise

    async def get_http_client(self) -> httpx.AsyncClient:
        """Возвращает аутентифицированный httpx клиент, обновляя токен при необходимости."""
        if not self._http_client or self._exp_at < datetime.now():
            self._logger.info('Getting new Marzban token...')
            token = await self._get_token()
            self._exp_at = datetime.now() + timedelta(minutes=self._config.marzban.token_expire - 1)
            
            headers = {
                "Authorization": f"Bearer {token}", 
                "Content-Type": "application/json", 
                "Accept": "application/json"
            }
            # Закрываем старый клиент, если он был, чтобы освободить ресурсы
            if self._http_client:
                await self._http_client.aclose()
            
            self._http_client = httpx.AsyncClient(base_url=self._base_url, headers=headers, verify=False)
            self._logger.info('New Marzban http client created.')
        return self._http_client

    async def add_user(self, username: str, expire_days: int) -> Dict[str, Any]:
        """Создает нового пользователя в Marzban."""
        client = await self.get_http_client()
        expire_timestamp = int((datetime.now() + timedelta(days=expire_days)).timestamp())

        json_body = {
            "username": username.lower(),
            "expire": expire_timestamp,
            "proxies": {
                "vless": {
                    "flow": "xtls-rprx-vision" # <--- ДОБАВЬТЕ ЭТУ СТРОКУ
                }
            },
            "inbounds": {
                "vless": ["VLESS-Reality"]
            }
        }

        response = await client.post("/api/user", json=json_body)
        response.raise_for_status()  # Вызовет исключение для кодов 4xx/5xx
        return response.json()

    async def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о пользователе из Marzban."""
        client = await self.get_http_client()
        try:
            response = await client.get(f"/api/user/{username.lower()}")
            if response.status_code == 200:
                return response.json()
            # Если юзер не найден, Marzban вернет 404, что будет поймано в except
            return None
        except httpx.HTTPStatusError as e:
            # Логируем только если это не 404 (юзер не найден)
            if e.response.status_code != 404:
                self._logger.error(f"Error getting user {username}: {e}", exc_info=True)
            return None
        except Exception as e:
            self._logger.error(f"An unexpected error occurred in get_user for {username}: {e}", exc_info=True)
            return None

    async def modify_user(self, username: str, expire_days: int) -> Dict[str, Any]:
        """
        Продлевает подписку существующего пользователя.
        Если пользователь не найден в Marzban - создает его с указанным сроком.
        """
        self._logger.info(f"Modifying/Ensuring subscription for user '{username}' for {expire_days} days.")
        
        # 1. Проверяем, существует ли пользователь
        user_exists = await self.get_user(username)
        
        # 2. Сценарий: Пользователь существует -> Продлеваем
        if user_exists:
            self._logger.info(f"User '{username}' exists. Extending subscription.")
            
            # Получаем текущую дату истечения из словаря
            current_expire_ts = user_exists.get('expire') or int(datetime.now().timestamp())
            
            # Рассчитываем новую дату
            if current_expire_ts > int(datetime.now().timestamp()):
                # Если подписка еще активна, добавляем дни к дате окончания
                new_expire_date = datetime.fromtimestamp(current_expire_ts) + timedelta(days=expire_days)
            else:
                # Если подписка истекла, добавляем дни к сегодняшней дате
                new_expire_date = datetime.now() + timedelta(days=expire_days)
            
            # Формируем тело запроса для изменения
            json_body = {"expire": int(new_expire_date.timestamp())}
            
            # Отправляем PUT запрос на изменение
            client = await self.get_http_client()
            response = await client.put(f"/api/user/{username.lower()}", json=json_body)
            response.raise_for_status()
            return response.json()

        # 3. Сценарий: Пользователя нет -> Создаем
        else:
            self._logger.warning(f"User '{username}' not found in Marzban. Creating a new user instead.")
            # Если пользователя нет, мы не можем его "изменить". Вместо этого мы вызываем
            # наш же метод add_user, чтобы создать его с нужным сроком.
            # Это избавляет от дублирования кода.
            return await self.add_user(username=username, expire_days=expire_days)

    # --- НОВЫЙ МЕТОД ---
        
    async def delete_user(self, username: str) -> bool:
        """Удаляет пользователя из Marzban."""
        client = await self.get_http_client()
        try:
            response = await client.delete(f"/api/user/{username.lower()}")
            response.raise_for_status()
            self._logger.info(f"Successfully deleted user '{username}' from Marzban.")
            return True
        except httpx.HTTPStatusError as e:
            # Если юзер уже удален (404), считаем это успехом
            if e.response.status_code == 404:
                self._logger.warning(f"Attempted to delete user '{username}', but they were not found (already deleted?).")
                return True
            self._logger.error(f"Failed to delete user '{username}': {e}", exc_info=True)
            return False
        except Exception as e:
            self._logger.error(f"An unexpected error occurred in delete_user for '{username}': {e}", exc_info=True)
            return False