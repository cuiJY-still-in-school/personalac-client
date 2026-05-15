import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def parse_invite_link(link: str) -> tuple[str, str] | tuple[None, None]:
    """解析邀请链接，返回 (server_url, invite_code)，失败返回 (None, None)"""
    link = link.strip()
    parsed = urlparse(link)
    m = re.match(r'^/join/([A-Z0-9]{6,12})$', parsed.path, re.IGNORECASE)
    if parsed.scheme in ('http', 'https') and parsed.netloc and m:
        server_url = f"{parsed.scheme}://{parsed.netloc}"
        return server_url, m.group(1).upper()
    return None, None


class PersonalACApi:
    def __init__(self, server_url: str, sync_token: str):
        self.server_url = server_url.rstrip("/")
        self.sync_token = sync_token
        self._session = requests.Session()
        self._session.headers.update({
            "x-sync-token": sync_token,
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> Optional[Any]:
        try:
            resp = self._session.get(
                f"{self.server_url}{path}", params=params, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("GET %s failed: %s", path, e)
            return None

    def _post(self, path: str, data: Any) -> Optional[Any]:
        try:
            resp = self._session.post(
                f"{self.server_url}{path}", json=data, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("POST %s failed: %s", path, e)
            return None

    def get_me(self) -> Optional[dict]:
        return self._get("/api/auth/me")

    def get_todos(self) -> list:
        result = self._get("/api/todos")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("data", result.get("todos", []))
        return []

    def get_mustdo(self) -> list:
        result = self._get("/api/todos", params={"status": "pending"})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("data", result.get("todos", []))
        return []

    def check_mustdo_complete(self) -> bool:
        try:
            pending = self.get_mustdo()
            if pending is None:
                return False
            must = [t for t in pending if t.get("mustdo") or t.get("must_do")]
            return len(must) == 0
        except Exception as e:
            logger.warning("check_mustdo_complete failed: %s", e)
            return False

    def report_activity(self, records: list) -> bool:
        if not records:
            return True
        result = self._post("/api/activity/report", {"records": records})
        return result is not None

    def get_client_config(self) -> dict:
        """拉取服务端下发的客户端配置（blocked_apps、mode 等）"""
        result = self._get("/api/client/config")
        if result and result.get("success"):
            return result.get("data", {})
        return {}

    def report_activity_v2(self, records: list) -> bool:
        if not records:
            return True
        result = self._post("/api/client/activity", {"records": records})
        return result is not None and result.get("success", False)

    def sync_mode(self, mode: str) -> None:
        self._post("/api/client/mode", {"mode": mode})

    # ── 邀请码激活流程 ─────────────────────────────────────────────────────

    @staticmethod
    def get_invite_info(server_url: str, invite_code: str) -> Optional[dict]:
        """获取邀请码对应的学生信息（无需登录）"""
        try:
            resp = requests.get(
                f"{server_url.rstrip('/')}/api/auth/join/{invite_code}",
                timeout=10
            )
            data = resp.json()
            if data.get("success"):
                return data.get("data")
        except Exception as e:
            logger.warning("get_invite_info failed: %s", e)
        return None

    @staticmethod
    def accept_invite(server_url: str, invite_code: str, display_name: str, password: str) -> Optional[str]:
        """激活账号，成功返回 sync_token"""
        try:
            resp = requests.post(
                f"{server_url.rstrip('/')}/api/auth/join/{invite_code}",
                json={"displayName": display_name, "password": password},
                timeout=10
            )
            data = resp.json()
            if data.get("success") and data.get("syncToken"):
                return data["syncToken"]
        except Exception as e:
            logger.warning("accept_invite failed: %s", e)
        return None
