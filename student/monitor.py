import sys
import time
import logging
from datetime import datetime
from typing import Optional

import psutil
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


def _get_foreground_info_windows() -> tuple[str, str]:
    try:
        import ctypes
        import ctypes.wintypes
        import win32process
        import win32gui

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "", ""
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc = psutil.Process(pid)
            return proc.name(), title
        except psutil.NoSuchProcess:
            return "", title
    except Exception as e:
        logger.debug("win32 foreground query failed: %s", e)
        return "", ""


def _get_foreground_info_fallback() -> tuple[str, str]:
    try:
        top = max(
            (p for p in psutil.process_iter(["name", "cpu_percent"]) if p.info["cpu_percent"] is not None),
            key=lambda p: p.info["cpu_percent"],
            default=None,
        )
        if top:
            return top.info["name"], ""
    except Exception:
        pass
    return "", ""


def get_foreground_info() -> tuple[str, str]:
    if sys.platform == "win32":
        return _get_foreground_info_windows()
    return _get_foreground_info_fallback()


class _Session:
    def __init__(self, app_name: str, window_title: str):
        self.app_name = app_name
        self.window_title = window_title
        self.start_time: datetime = datetime.now()
        self.end_time: Optional[datetime] = None

    def finish(self) -> dict:
        self.end_time = datetime.now()
        duration = int((self.end_time - self.start_time).total_seconds())
        return {
            "app_name": self.app_name,
            "window_title": self.window_title,
            "duration_seconds": max(duration, 1),
            "timestamp": self.start_time.isoformat(),
        }


class ActivityMonitor(QThread):
    activity_changed = pyqtSignal(str, str)
    blocked_app_detected = pyqtSignal(str)

    def __init__(self, blocked_apps: list = None, parent=None):
        super().__init__(parent)
        self.blocked_apps: list[str] = [a.lower() for a in (blocked_apps or [])]
        self._running = False
        self._pending: list[dict] = []
        self._current_session: Optional[_Session] = None

    def run(self):
        self._running = True
        while self._running:
            app_name, window_title = get_foreground_info()
            if app_name:
                if self.blocked_apps and app_name.lower() in self.blocked_apps:
                    self.blocked_app_detected.emit(app_name)

                if self._current_session is None or self._current_session.app_name != app_name:
                    if self._current_session is not None:
                        record = self._current_session.finish()
                        if record["duration_seconds"] >= 2:
                            self._pending.append(record)
                    self._current_session = _Session(app_name, window_title)
                    self.activity_changed.emit(app_name, window_title)
                else:
                    self._current_session.window_title = window_title

            time.sleep(3)

    def stop(self):
        self._running = False
        if self._current_session is not None:
            record = self._current_session.finish()
            if record["duration_seconds"] >= 2:
                self._pending.append(record)
            self._current_session = None
        self.wait(3000)

    def get_pending_records(self) -> list[dict]:
        records = list(self._pending)
        self._pending.clear()
        return records

    def update_blocked_apps(self, blocked_apps: list):
        self.blocked_apps = [a.lower() for a in blocked_apps]
