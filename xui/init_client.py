# xui/init_client.py (ФИНАЛЬНАЯ ВЕРСИЯ. РУЧНАЯ. РАБОЧАЯ.)

import aiohttp
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config import Config

class XUIClient:
    def __init__(self, config: Config, logger, verify_ssl: bool = False):
        xui_config = config.xui
        self._host = xui_config.host.rstrip('/')
        self._username = xui_config.username
        self._password = xui_config.password
        self.inbound_id = xui_config.inbound_id
        self.config = config
        self._logger = logger
        self._verify_ssl = verify_ssl
        self._session: Optional[aiohttp.ClientSession] = None
        self._is_logged_in = False
        self._inbound_cache: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=self._verify_ssl), headers={"Accept": "application/json"})
            self._is_logged_in = False
        return self._session

    async def login(self) -> bool:
        session = await self._get_session()
        if self._is_logged_in: return True
        self._logger.info("Logging in to 3x-ui panel...")
        try:
            async with session.post(f"{self._host}/login", data={"username": self._username, "password": self._password}) as response:
                if response.status == 200:
                    self._logger.info("Login successful.")
                    self._is_logged_in = True
                    return True
                else: return False
        except Exception: return False

    async def _ensure_logged_in(self):
        if not self._is_logged_in:
            await self.login()

    async def _get_inbound_data(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        now = datetime.now()
        if not force_refresh and self._inbound_cache and self._cache_time and (now - self._cache_time).total_seconds() < 5:
            return self._inbound_cache
        await self._ensure_logged_in()
        session = await self._get_session()
        try:
            async with session.get(f"{self._host}/panel/api/inbounds/get/{self.inbound_id}") as response:
                response.raise_for_status()
                data = await response.json()
                if data.get("success"):
                    self._inbound_cache = data.get("obj"); self._cache_time = now
                    return self._inbound_cache
        except Exception: return None
        return None

    async def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        inbound_data = await self._get_inbound_data()
        if not inbound_data: return None
        try:
            client_settings = json.loads(inbound_data.get("settings", "{}"))
            for client in client_settings.get("clients", []):
                if client.get("email", "").lower() == username.lower():
                    return client
            return None
        except (json.JSONDecodeError, TypeError): return None

    async def get_user_config_link(self, username: str) -> Optional[str]:
        """
        Собирает ссылку-конфиг для пользователя вручную, используя данные из API и домен из конфига.
        С подробным логированием каждого шага.
        """
        self._logger.info(f"Attempting to build config link for user '{username}'...")
    
        user_data = await self.get_user(username)
        if not user_data or not user_data.get("id"):
        # Логируем ошибку перед выходом
            self._logger.error(f"Cannot get config link: user '{username}' not found or has no UUID.")
            return None
    
        user_uuid = user_data["id"]
        self._logger.debug(f"Found user '{username}' with UUID: {user_uuid}")

        try:
            inbound_data = await self._get_inbound_data()
            if not inbound_data:
                self._logger.error(f"Cannot get config link for '{username}': failed to fetch inbound data for ID {self.inbound_id}.")
                return None
        
            self._logger.debug("Successfully fetched inbound data.")
        
            protocol = inbound_data.get("protocol", "vless")
            domain = self.config.webhook.domain
            port = inbound_data.get("port", 443)
        
            stream_settings = json.loads(inbound_data.get("streamSettings", "{}"))
            security = stream_settings.get("security", "none")
        
            self._logger.debug(f"Building link with params: protocol={protocol}, domain={domain}, port={port}, security={security}")
        
            link = f"{protocol}://{user_uuid}@{domain}:{port}?type={stream_settings.get('network', 'tcp')}"

            if security == 'reality':
                self._logger.debug("Inbound security is 'reality', parsing reality settings...")
                reality_settings = stream_settings.get("realitySettings", {})
                inner_settings = reality_settings.get("settings", {})
                server_names = reality_settings.get('serverNames', [''])
                short_ids = reality_settings.get('shortIds', [''])

                sni = server_names[0] if server_names else reality_settings.get('dest', '').split(':')[0]
                pbk = inner_settings.get('publicKey', '')
                sid = short_ids[0] if short_ids else ''
                fp = inner_settings.get('fingerprint', 'chrome')
            
                self._logger.debug(f"Reality params parsed: sni='{sni}', pbk='{pbk[:5]}...', sid='{sid}'")

                if not all([sni, pbk, sid]):
                # Логируем критическую ошибку, если не хватает данных
                    self._logger.error(f"Cannot build REALITY link for inbound {self.inbound_id}: SNI, PublicKey, or ShortID is missing in panel settings.")
                    return f"Ошибка: неполные настройки REALITY в панели. Обратитесь к администратору."

                link += f"&security=reality&fp={fp}&pbk={pbk}&sni={sni}&sid={sid}"
        
            bot_name = getattr(self.config.tg_bot, 'bot_name', 'VPN') # Безопасное получение имени бота
            link += f"#{bot_name}_{user_data.get('email', '')}"
        
            self._logger.info(f"Successfully built config link for user '{username}'.")
            return link
        
        except Exception as e:
        # Логируем любую непредвиденную ошибку
            self._logger.error(f"Unexpected error while building config link for '{username}': {e}", exc_info=True)
            return None

    async def add_user(self, username: str, expire_days: int, traffic_gb: int = 1000) -> Optional[str]:
        await self._ensure_logged_in()
        session = await self._get_session()
        expire_time = int((datetime.now() + timedelta(days=expire_days)).timestamp() * 1000)
        traffic_bytes = traffic_gb * 1024 * 1024 * 1024
        client_uuid = str(uuid.uuid4())
        new_client_settings = {"id": client_uuid, "email": username.lower(), "enable": True, "expiryTime": expire_time, "totalGB": traffic_bytes, "flow": ""}
        payload = {"id": self.inbound_id, "settings": json.dumps({"clients": [new_client_settings]})}
        try:
            async with session.post(f"{self._host}/panel/api/inbounds/addClient", json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                if result.get("success"):
                    await self._get_inbound_data(force_refresh=True)
                    return client_uuid
        except Exception: return None

    async def _update_user(self, user_data: Dict[str, Any]) -> Optional[str]:
        await self._ensure_logged_in()
        session = await self._get_session()
        user_uuid = user_data.get("id")
        payload = {"id": self.inbound_id, "settings": json.dumps({"clients": [user_data]})}
        try:
            async with session.post(f"{self._host}/panel/api/inbounds/updateClient/{user_uuid}", json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                if result.get("success"):
                    await self._get_inbound_data(force_refresh=True)
                    return user_uuid
        except Exception: return None

    async def modify_user(self, username: str, expire_days: int, traffic_gb: int = 1000) -> Optional[str]:
        existing_user = await self.get_user(username.lower())
        if existing_user:
            current_expire_ms = existing_user.get('expiryTime', 0)
            now_ms = int(datetime.now().timestamp() * 1000)
            new_expire_date = (datetime.fromtimestamp(current_expire_ms / 1000) if current_expire_ms > now_ms else datetime.now()) + timedelta(days=expire_days)
            updated_user_data = existing_user.copy()
            updated_user_data.update({"enable": True, "expiryTime": int(new_expire_date.timestamp() * 1000), "totalGB": traffic_gb * 1024 * 1024 * 1024})
            return await self._update_user(updated_user_data)
        else:
            return await self.add_user(username=username.lower(), expire_days=expire_days, traffic_gb=traffic_gb)

    async def delete_user(self, username: str) -> bool:
        await self._ensure_logged_in()
        session = await self._get_session()
        user = await self.get_user(username)
        if not user: return True
        user_uuid = user.get("id")
        try:
            async with session.post(f"{self._host}/panel/api/inbounds/{self.inbound_id}/delClient/{user_uuid}") as response:
                response.raise_for_status()
                result = await response.json()
                if result.get("success"):
                    await self._get_inbound_data(force_refresh=True)
                    return True
        except Exception: return False
        return False

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()