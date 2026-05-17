"""系统托盘图标 + 退出身份验证"""
import logging
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QFont
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QApplication,
)

logger = logging.getLogger(__name__)

_QSS_DIALOG = """
QDialog { background: #F9F7F4; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; }
QLabel { color: #1A1815; }
QLineEdit {
    background: white; border: 1.5px solid #D4D0CA; border-radius: 8px;
    padding: 9px 12px; font-size: 13px; color: #1A1815;
}
QLineEdit:focus { border-color: #D97757; }
QPushButton#primary {
    background: #D97757; color: white; border: none; border-radius: 8px;
    padding: 10px 0; font-size: 13px; font-weight: 600;
}
QPushButton#primary:hover { background: #C4663E; }
QPushButton#primary:disabled { background: #D4D0CA; color: #9A9690; }
QPushButton#secondary {
    background: transparent; border: 1.5px solid #D4D0CA; border-radius: 8px;
    padding: 10px 0; font-size: 13px; color: #6B6560;
}
QPushButton#secondary:hover { border-color: #9A9690; }
"""

_QSS_MENU = """
QMenu {
    background: #1C1917; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 4px;
}
QMenu::item {
    color: #F9F7F4; padding: 8px 18px 8px 12px;
    font-size: 13px; border-radius: 6px;
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
}
QMenu::item:selected { background: rgba(217,119,87,0.22); }
QMenu::item:disabled { color: rgba(249,247,244,0.3); }
QMenu::separator { height: 1px; background: rgba(255,255,255,0.08); margin: 3px 8px; }
"""


def _make_icon(size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # coral rounded square
    p.setBrush(QBrush(QColor("#D97757")))
    p.setPen(Qt.PenStyle.NoPen)
    r = size // 6
    p.drawRoundedRect(0, 0, size, size, r, r)
    # white "P" letter
    font = QFont("Segoe UI", size * 38 // 100, QFont.Weight.Bold)
    p.setFont(font)
    p.setPen(QPen(QColor("white")))
    p.drawText(0, 0, size, size, Qt.AlignmentFlag.AlignCenter, "P")
    p.end()
    return QIcon(pm)


class _GuardianVerifyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("退出 PersonalAC")
        self.setFixedSize(340, 260)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(_QSS_DIALOG)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 22)
        lay.setSpacing(0)

        title = QLabel("需要监护人验证")
        title.setStyleSheet("font-size: 16px; font-weight: 800; letter-spacing: -0.3px;")
        lay.addWidget(title)
        lay.addSpacing(6)

        hint = QLabel("输入监护人的邮箱和密码来关闭 PersonalAC")
        hint.setStyleSheet("font-size: 12px; color: #9A9690;")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addSpacing(22)

        email_lbl = QLabel("监护人邮箱")
        email_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #6B6560;")
        lay.addWidget(email_lbl)
        lay.addSpacing(5)
        self._email = QLineEdit()
        self._email.setPlaceholderText("guardian@example.com")
        lay.addWidget(self._email)
        lay.addSpacing(12)

        pw_lbl = QLabel("密码")
        pw_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #6B6560;")
        lay.addWidget(pw_lbl)
        lay.addSpacing(5)
        self._pw = QLineEdit()
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw.setPlaceholderText("监护人密码")
        self._pw.returnPressed.connect(self._try_confirm)
        lay.addWidget(self._pw)
        lay.addSpacing(6)

        self._status = QLabel("")
        self._status.setStyleSheet("font-size: 11px; color: #E53E3E; min-height: 14px;")
        lay.addWidget(self._status)
        lay.addSpacing(14)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel = QPushButton("取消")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        self._confirm_btn = QPushButton("确认退出")
        self._confirm_btn.setObjectName("primary")
        self._confirm_btn.clicked.connect(self._try_confirm)
        btn_row.addWidget(self._confirm_btn)
        lay.addLayout(btn_row)

    def get_credentials(self) -> tuple[str, str]:
        return self._email.text().strip(), self._pw.text()

    def show_error(self, msg: str):
        self._status.setText(msg)
        self._confirm_btn.setEnabled(True)
        self._confirm_btn.setText("确认退出")

    def _try_confirm(self):
        email, pw = self.get_credentials()
        if not email or not pw:
            self._status.setText("请填写邮箱和密码")
            return
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setText("验证中…")
        self._status.setText("")
        self.accept()  # caller handles actual verification


class SystemTray(QObject):
    show_pet = pyqtSignal()
    show_main = pyqtSignal()
    open_drive_settings = pyqtSignal()
    quit_verified = pyqtSignal()   # emitted only after guardian password verified

    def __init__(self, parent=None):
        super().__init__(parent)
        self._api = None
        self._tray = QSystemTrayIcon(parent)
        self._tray.setIcon(_make_icon())
        self._tray.setToolTip("PersonalAC 学生端")
        self._tray.activated.connect(self._on_activated)
        self._build_menu()
        self._tray.show()

    def set_api(self, api):
        self._api = api

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet(_QSS_MENU)

        self._act_pet = menu.addAction("显示宠物")
        self._act_pet.triggered.connect(self.show_pet)

        self._act_main = menu.addAction("打开学习界面")
        self._act_main.triggered.connect(self.show_main)

        self._act_drive = menu.addAction("☁️ 云盘设置…")
        # 信号在 app.py 里连接
        self._act_drive.triggered.connect(self.open_drive_settings)

        menu.addSeparator()

        act_quit = menu.addAction("退出 PersonalAC…")
        act_quit.triggered.connect(self._on_quit)

        self._tray.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_pet.emit()

    def _on_quit(self):
        dlg = _GuardianVerifyDialog()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        email, password = dlg.get_credentials()
        if not email or not password:
            return
        # Verify with server
        if self._api:
            try:
                result = self._api._post("/api/client/guardian-verify", {"email": email, "password": password})
                if result and result.get("success"):
                    self.quit_verified.emit()
                else:
                    err = (result or {}).get("error", "邮箱或密码错误")
                    dlg.show_error(err)
                    self.notify("验证失败", err, QSystemTrayIcon.MessageIcon.Warning)
            except Exception as e:
                logger.warning("guardian verify error: %s", e)
                # Server unreachable — still allow quit
                self.quit_verified.emit()
        else:
            self.quit_verified.emit()

    def notify(self, title: str, message: str,
               icon=QSystemTrayIcon.MessageIcon.Information,
               duration_ms: int = 5000):
        if self._tray.isVisible() and self._tray.supportsMessages():
            self._tray.showMessage(title, message, icon, duration_ms)

    def update_tooltip(self, mode: str, student_name: str):
        mode_map = {"locked": "专注模式", "pet": "宠物模式", "free": "自由模式"}
        self._tray.setToolTip(
            f"PersonalAC — {student_name} · {mode_map.get(mode, mode)}"
        )

    def set_pet_visible(self, visible: bool):
        self._act_pet.setText("隐藏宠物" if visible else "显示宠物")
