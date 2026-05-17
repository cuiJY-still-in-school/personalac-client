import json
import os
from typing import Any


class Config:
    def __init__(self):
        self.server_url: str = "http://localhost:7575"
        self.sync_token: str = ""
        self.student_id: str = ""
        self.student_name: str = ""
        self.mode: str = "locked"
        self.pet_position: list = [None, None]
        self.blocked_apps: list = []
        self.drive_enabled: bool = False
        self.drive_path: str = ''
        self.drive_last_pull: int = 0

    @staticmethod
    def config_path() -> str:
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "PersonalAC", "config.json")

    @staticmethod
    def get_default() -> "Config":
        return Config()

    def load(self) -> "Config":
        path = self.config_path()
        if not os.path.exists(path):
            return self
        try:
            with open(path, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            self.server_url = data.get("server_url", self.server_url)
            self.sync_token = data.get("sync_token", self.sync_token)
            self.student_id = data.get("student_id", self.student_id)
            self.student_name = data.get("student_name", self.student_name)
            self.mode = data.get("mode", self.mode)
            self.pet_position   = data.get("pet_position",   self.pet_position)
            self.blocked_apps   = data.get("blocked_apps",   self.blocked_apps)
            self.drive_enabled  = data.get("drive_enabled",  self.drive_enabled)
            self.drive_path     = data.get("drive_path",     self.drive_path)
            self.drive_last_pull = data.get("drive_last_pull", self.drive_last_pull)
        except (json.JSONDecodeError, OSError):
            pass
        return self

    def save(self) -> bool:
        path = self.config_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {
                "server_url": self.server_url,
                "sync_token": self.sync_token,
                "student_id": self.student_id,
                "student_name": self.student_name,
                "mode": self.mode,
                "pet_position":    self.pet_position,
                "blocked_apps":    self.blocked_apps,
                "drive_enabled":   self.drive_enabled,
                "drive_path":      self.drive_path,
                "drive_last_pull": self.drive_last_pull,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def is_configured(self) -> bool:
        return bool(self.server_url and self.sync_token)
