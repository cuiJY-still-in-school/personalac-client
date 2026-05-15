import sys
import logging
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from common.config import Config
from common.api import PersonalACApi

logger = logging.getLogger(__name__)


_DIALOG_QSS = """
QDialog {
    background: #F9F7F4;
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
}
QLabel { color: #1A1815; }
QLineEdit {
    background: white;
    border: 1.5px solid #D4D0CA;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 13px;
    color: #1A1815;
}
QLineEdit:focus { border-color: #D97757; outline: none; }
QPushButton#primary {
    background: #D97757; color: white; border: none;
    border-radius: 8px; padding: 10px 0;
    font-size: 14px; font-weight: 600;
}
QPushButton#primary:hover { background: #C4663E; }
QPushButton#primary:disabled { background: #D4D0CA; color: #9A9690; }
QPushButton#link {
    background: transparent; border: none;
    color: #D97757; font-size: 12px; padding: 0;
    text-decoration: underline;
}
QPushButton#link:hover { color: #C4663E; }
"""


class SetupDialog(QDialog):
    """首次启动配置弹窗。

    两种方式：
      1. 粘贴邀请链接  http://server/join/XXXXXXXX  → 自动激活账号
      2. 直接输入服务器地址 + 同步码（已有账号）
    """

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._invite_server: str = ''
        self._invite_code: str = ''
        self._invite_info: dict = {}
        self.setWindowTitle("PersonalAC")
        self.setFixedSize(400, 460)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(_DIALOG_QSS)
        self._build_ui()

    def _build_ui(self):
        from PyQt6.QtWidgets import QStackedWidget, QFrame
        self._stack = QStackedWidget(self)
        self._stack.setGeometry(0, 0, 400, 460)

        self._page_invite = self._build_page_invite()
        self._page_password = self._build_page_password()
        self._page_token = self._build_page_token()

        self._stack.addWidget(self._page_invite)    # 0
        self._stack.addWidget(self._page_password)  # 1
        self._stack.addWidget(self._page_token)     # 2

    # ── page 0: 邀请链接输入 ──────────────────────────────────────────────
    def _build_page_invite(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(36, 36, 36, 28)
        lay.setSpacing(0)

        # Logo / title
        logo = QLabel("PersonalAC")
        logo.setStyleSheet("font-size: 22px; font-weight: 800; color: #1A1815; letter-spacing: -0.5px;")
        lay.addWidget(logo)
        lay.addSpacing(6)

        sub = QLabel("让学习更有计划，让成长看得见")
        sub.setStyleSheet("font-size: 13px; color: #9A9690;")
        lay.addWidget(sub)
        lay.addSpacing(32)

        invite_label = QLabel("粘贴邀请链接")
        invite_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #6B6560; margin-bottom: 4px;")
        lay.addWidget(invite_label)
        lay.addSpacing(6)

        self._invite_input = QLineEdit()
        self._invite_input.setPlaceholderText("http://server.com/join/XXXXXXXX")
        self._invite_input.textChanged.connect(self._on_invite_changed)
        lay.addWidget(self._invite_input)
        lay.addSpacing(8)

        self._invite_hint = QLabel("由家长/老师从管理网站复制后发给你")
        self._invite_hint.setStyleSheet("font-size: 11px; color: #B0ADA8;")
        lay.addWidget(self._invite_hint)
        lay.addSpacing(20)

        self._invite_btn = QPushButton("下一步")
        self._invite_btn.setObjectName("primary")
        self._invite_btn.setFixedHeight(44)
        self._invite_btn.setEnabled(False)
        self._invite_btn.clicked.connect(self._on_invite_next)
        lay.addWidget(self._invite_btn)
        lay.addSpacing(16)

        sep = QLabel("─────── 或者 ───────")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep.setStyleSheet("font-size: 11px; color: #C8C5BF;")
        lay.addWidget(sep)
        lay.addSpacing(10)

        token_btn = QPushButton("已有账号，直接输入同步码")
        token_btn.setObjectName("link")
        token_btn.clicked.connect(lambda: self._stack.setCurrentIndex(2))
        lay.addWidget(token_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        lay.addStretch()
        return page

    # ── page 1: 邀请激活 → 设置密码 ──────────────────────────────────────
    def _build_page_password(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(36, 36, 36, 28)
        lay.setSpacing(0)

        back_btn = QPushButton("← 返回")
        back_btn.setObjectName("link")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        lay.addWidget(back_btn)
        lay.addSpacing(16)

        self._pw_greeting = QLabel("你好！")
        self._pw_greeting.setStyleSheet("font-size: 20px; font-weight: 800; color: #1A1815;")
        lay.addWidget(self._pw_greeting)
        lay.addSpacing(4)

        self._pw_sub = QLabel("设置一个登录密码来激活账号")
        self._pw_sub.setStyleSheet("font-size: 13px; color: #9A9690;")
        lay.addWidget(self._pw_sub)
        lay.addSpacing(28)

        name_label = QLabel("你的名字")
        name_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #6B6560;")
        lay.addWidget(name_label)
        lay.addSpacing(6)
        self._pw_name = QLineEdit()
        self._pw_name.setPlaceholderText("显示名称")
        lay.addWidget(self._pw_name)
        lay.addSpacing(14)

        pw_label = QLabel("设置密码")
        pw_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #6B6560;")
        lay.addWidget(pw_label)
        lay.addSpacing(6)
        self._pw_input = QLineEdit()
        self._pw_input.setPlaceholderText("至少 6 位")
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self._pw_input)
        lay.addSpacing(14)

        pw2_label = QLabel("确认密码")
        pw2_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #6B6560;")
        lay.addWidget(pw2_label)
        lay.addSpacing(6)
        self._pw_confirm = QLineEdit()
        self._pw_confirm.setPlaceholderText("再次输入密码")
        self._pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self._pw_confirm)
        lay.addSpacing(8)

        self._pw_status = QLabel("")
        self._pw_status.setStyleSheet("font-size: 11px; color: #E53E3E;")
        lay.addWidget(self._pw_status)
        lay.addSpacing(16)

        self._pw_btn = QPushButton("激活账号")
        self._pw_btn.setObjectName("primary")
        self._pw_btn.setFixedHeight(44)
        self._pw_btn.clicked.connect(self._on_activate)
        lay.addWidget(self._pw_btn)

        lay.addStretch()
        return page

    # ── page 2: 手动输入同步码 ────────────────────────────────────────────
    def _build_page_token(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(36, 36, 36, 28)
        lay.setSpacing(0)

        back_btn = QPushButton("← 返回")
        back_btn.setObjectName("link")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        lay.addWidget(back_btn)
        lay.addSpacing(16)

        title = QLabel("直接连接")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #1A1815;")
        lay.addWidget(title)
        lay.addSpacing(4)
        sub = QLabel("输入服务器地址和同步码")
        sub.setStyleSheet("font-size: 13px; color: #9A9690;")
        lay.addWidget(sub)
        lay.addSpacing(28)

        url_label = QLabel("服务器地址")
        url_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #6B6560;")
        lay.addWidget(url_label)
        lay.addSpacing(6)
        self._token_url = QLineEdit()
        self._token_url.setPlaceholderText("http://localhost:7575")
        lay.addWidget(self._token_url)
        lay.addSpacing(14)

        tk_label = QLabel("同步码")
        tk_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #6B6560;")
        lay.addWidget(tk_label)
        lay.addSpacing(6)
        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText("粘贴同步码")
        lay.addWidget(self._token_input)
        lay.addSpacing(8)

        self._token_status = QLabel("")
        self._token_status.setStyleSheet("font-size: 11px; color: #E53E3E;")
        lay.addWidget(self._token_status)
        lay.addSpacing(16)

        self._token_btn = QPushButton("连接")
        self._token_btn.setObjectName("primary")
        self._token_btn.setFixedHeight(44)
        self._token_btn.clicked.connect(self._on_token_connect)
        lay.addWidget(self._token_btn)

        lay.addStretch()
        return page

    # ── 逻辑 ──────────────────────────────────────────────────────────────
    def _on_invite_changed(self, text: str):
        from common.api import parse_invite_link
        server, code = parse_invite_link(text)
        self._invite_btn.setEnabled(bool(server and code))
        if server and code:
            self._invite_hint.setText(f"服务器：{server}  邀请码：{code}")
            self._invite_hint.setStyleSheet("font-size: 11px; color: #22C55E;")
        else:
            self._invite_hint.setText("由家长/老师从管理网站复制后发给你")
            self._invite_hint.setStyleSheet("font-size: 11px; color: #B0ADA8;")

    def _on_invite_next(self):
        from common.api import parse_invite_link, PersonalACApi
        server, code = parse_invite_link(self._invite_input.text())
        if not server or not code:
            return

        self._invite_btn.setEnabled(False)
        self._invite_btn.setText("验证中…")

        info = PersonalACApi.get_invite_info(server, code)
        self._invite_btn.setEnabled(True)
        self._invite_btn.setText("下一步")

        if not info:
            self._invite_hint.setText("邀请码无效或服务器无法连接")
            self._invite_hint.setStyleSheet("font-size: 11px; color: #E53E3E;")
            return

        self._invite_server = server
        self._invite_code = code
        self._invite_info = info

        self._pw_greeting.setText(f"你好，{info.get('studentName', '')}！")
        self._pw_name.setText(info.get('studentName', ''))
        self._pw_status.setText("")
        self._stack.setCurrentIndex(1)

    def _on_activate(self):
        from common.api import PersonalACApi
        name = self._pw_name.text().strip()
        pw = self._pw_input.text()
        pw2 = self._pw_confirm.text()

        if not name:
            self._pw_status.setText("请填写名字")
            return
        if len(pw) < 6:
            self._pw_status.setText("密码至少 6 位")
            return
        if pw != pw2:
            self._pw_status.setText("两次密码不一致")
            return

        self._pw_btn.setEnabled(False)
        self._pw_btn.setText("激活中…")
        self._pw_status.setText("")

        token = PersonalACApi.accept_invite(self._invite_server, self._invite_code, name, pw)
        if not token:
            self._pw_btn.setEnabled(True)
            self._pw_btn.setText("激活账号")
            self._pw_status.setText("激活失败，请重试")
            return

        api = PersonalACApi(self._invite_server, token)
        me = api.get_me()

        self.config.server_url = self._invite_server
        self.config.sync_token = token
        self.config.student_name = name
        self.config.student_id = (me or {}).get('data', {}).get('id', '') if me else ''
        self.config.save()
        self.accept()

    def _on_token_connect(self):
        from common.api import PersonalACApi
        url = self._token_url.text().strip().rstrip('/')
        token = self._token_input.text().strip()
        if not url or not token:
            self._token_status.setText("请填写服务器地址和同步码")
            return

        self._token_btn.setEnabled(False)
        self._token_btn.setText("连接中…")
        self._token_status.setText("")

        api = PersonalACApi(url, token)
        me = api.get_me()
        self._token_btn.setEnabled(True)
        self._token_btn.setText("连接")

        if not me or not me.get('success'):
            self._token_status.setText("连接失败，请检查地址和同步码")
            return

        data = me.get('data', {})
        self.config.server_url = url
        self.config.sync_token = token
        self.config.student_name = data.get('displayName') or data.get('username', '')
        self.config.student_id = data.get('id', '')
        self.config.save()
        self.accept()


class StudentApp:
    def __init__(self):
        self._qt_app: QApplication | None = None
        self._config = Config()
        self._api: PersonalACApi | None = None
        self._monitor = None
        self._main_window = None
        self._pet_window = None
        self._activity_sync_timer: QTimer | None = None

    def run(self) -> int:
        self._qt_app = QApplication(sys.argv)
        self._qt_app.setApplicationName("PersonalAC")
        self._qt_app.setQuitOnLastWindowClosed(False)

        self._config.load()

        if not self._config.is_configured():
            dialog = SetupDialog(self._config)
            result = dialog.exec()
            if result != QDialog.DialogCode.Accepted:
                return 0

        self._api = PersonalACApi(self._config.server_url, self._config.sync_token)

        me = self._api.get_me()
        if me is None:
            dialog = SetupDialog(self._config)
            result = dialog.exec()
            if result != QDialog.DialogCode.Accepted:
                return 0
            self._api = PersonalACApi(self._config.server_url, self._config.sync_token)

        self._pull_server_config()
        self._start_monitor()
        self._start_activity_sync()

        complete = self._config.mode in ('pet', 'free') or self._api.check_mustdo_complete()
        if complete or self._config.mode in ("pet", "free"):
            self._show_pet()
        else:
            self._show_locked()

        return self._qt_app.exec()

    def _pull_server_config(self):
        """从服务端拉取 blocked_apps 等配置，更新本地 config"""
        if not self._api:
            return
        cfg = self._api.get_client_config()
        if cfg:
            self._config.blocked_apps = cfg.get('blocked_apps', [])
            # 如果服务端说当前模式，尊重它
            server_mode = cfg.get('mode')
            if server_mode in ('locked', 'pet', 'free'):
                self._config.mode = server_mode
            self._config.save()

    def _start_monitor(self):
        from student.monitor import ActivityMonitor
        self._monitor = ActivityMonitor(self._config.blocked_apps)
        self._monitor.blocked_app_detected.connect(self._on_blocked_app)
        self._monitor.start()

    def _start_activity_sync(self):
        self._activity_sync_timer = QTimer()
        self._activity_sync_timer.setInterval(5 * 60 * 1000)
        self._activity_sync_timer.timeout.connect(self._sync_activity)
        self._activity_sync_timer.start()

    def _sync_activity(self):
        if self._monitor and self._api:
            records = self._monitor.get_pending_records()
            if records:
                self._api.report_activity(records)

    def _show_locked(self):
        from student.main_window import MainWindow
        self._main_window = MainWindow(self._config, self._api)
        self._main_window.mustdo_complete.connect(self._on_mustdo_complete)
        self._main_window.show()

        if self._pet_window and self._pet_window.isVisible():
            self._pet_window.hide()

    def _show_pet(self):
        from student.pet import PetWindow
        if self._pet_window is None:
            self._pet_window = PetWindow(self._config)
            self._pet_window.open_main.connect(self._on_open_main)
        self._pet_window.show()

        if self._main_window and self._main_window.isVisible():
            self._main_window.hide()

    def _on_mustdo_complete(self):
        self._config.mode = "pet"
        self._config.save()
        self._sync_activity()
        if self._api:
            self._api.sync_mode("pet")
        self._show_pet()

    def _on_open_main(self):
        if self._main_window is None:
            from student.main_window import MainWindow
            self._main_window = MainWindow(self._config, self._api)
            self._main_window.mustdo_complete.connect(self._on_mustdo_complete)
        self._main_window.show()
        self._main_window.activateWindow()

    def _on_blocked_app(self, process_name: str):
        logger.info("Blocked app detected: %s", process_name)
        if sys.platform == "win32":
            try:
                import psutil
                for proc in psutil.process_iter(["name", "pid"]):
                    if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                        proc.kill()
                        logger.info("Killed blocked process: %s (pid %s)", process_name, proc.pid)
                        break
            except Exception as e:
                logger.warning("Failed to kill blocked process %s: %s", process_name, e)
