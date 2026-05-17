import sys
from datetime import date
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QColor, QPainter, QFont, QPen, QBrush
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QSizePolicy, QStatusBar,
)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from common.config import Config
from common.api import PersonalACApi

_SHIELD_SVG = """
<svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M11 2L3 5.5V11C3 15.418 6.582 19 11 20C15.418 19 19 15.418 19 11V5.5L11 2Z"
        fill="#D97757" stroke="#F5C49A" stroke-width="0.8"/>
  <path d="M8 11l2 2 4-4" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


class _LogoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(160)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(8)

        try:
            from PyQt6.QtSvgWidgets import QSvgWidget
            from PyQt6.QtCore import QByteArray
            svg = QSvgWidget()
            svg.load(QByteArray(_SHIELD_SVG.encode()))
            svg.setFixedSize(22, 22)
            layout.addWidget(svg)
        except ImportError:
            pass

        text = QLabel("PersonalAC")
        text.setStyleSheet(
            "color: #F9F7F4; font-size: 15px; font-weight: 700;"
            "font-family: 'Segoe UI', 'PingFang SC', sans-serif; letter-spacing: 0.5px;"
        )
        layout.addWidget(text)
        layout.addStretch()


class _StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._ok = True

    def set_ok(self, ok: bool):
        self._ok = ok
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        color = QColor("#4ADE80") if self._ok else QColor("#F87171")
        p.setBrush(QBrush(color))
        p.drawEllipse(0, 0, 10, 10)
        p.end()


class _ProgressBadge(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._done = 0
        self._total = 0
        self._refresh()

    def update_progress(self, done: int, total: int):
        self._done = done
        self._total = total
        self._refresh()

    def _refresh(self):
        text = f"任务 {self._done}/{self._total}"
        color = "#4ADE80" if self._done >= self._total > 0 else "#D97757"
        self.setText(text)
        self.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 600;"
            f"background: rgba(255,255,255,0.08); border-radius: 10px;"
            f"padding: 2px 10px; font-family: 'Segoe UI', 'PingFang SC', sans-serif;"
        )


class TopBar(QWidget):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet("background: #1A1815;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(0)

        self._logo = _LogoWidget()
        layout.addWidget(self._logo)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 6, 0, 6)
        center_layout.setSpacing(1)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._name_label = QLabel(config.student_name or "学生")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet(
            "color: #F9F7F4; font-size: 13px; font-weight: 600;"
            "font-family: 'Segoe UI', 'PingFang SC', sans-serif;"
        )
        self._date_label = QLabel(date.today().strftime("%Y年%m月%d日"))
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_label.setStyleSheet(
            "color: rgba(249,247,244,0.5); font-size: 11px;"
            "font-family: 'Segoe UI', 'PingFang SC', sans-serif;"
        )
        center_layout.addWidget(self._name_label)
        center_layout.addWidget(self._date_label)
        layout.addWidget(center, 1)

        right = QWidget()
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._badge = _ProgressBadge()
        self._dot = _StatusDot()
        right_layout.addWidget(self._badge)
        right_layout.addWidget(self._dot)
        layout.addWidget(right)

    def update_progress(self, done: int, total: int):
        self._badge.update_progress(done, total)

    def set_connection_ok(self, ok: bool):
        self._dot.set_ok(ok)


class BottomBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet("background: #111009; border-top: 1px solid rgba(255,255,255,0.06);")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        self._time_label = QLabel()
        self._time_label.setStyleSheet(
            "color: rgba(249,247,244,0.4); font-size: 11px;"
            "font-family: 'Segoe UI', 'Consolas', sans-serif;"
        )
        layout.addStretch()
        layout.addWidget(self._time_label)

        self._conn_dot = _StatusDot()
        self._conn_label = QLabel("已连接")
        self._conn_label.setStyleSheet(
            "color: rgba(249,247,244,0.4); font-size: 11px;"
            "font-family: 'Segoe UI', sans-serif;"
        )
        layout.addWidget(self._conn_dot)
        layout.addWidget(self._conn_label)

        self._clock = QTimer()
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick)
        self._clock.start()
        self._tick()

    def _tick(self):
        from datetime import datetime
        self._time_label.setText(datetime.now().strftime("%H:%M:%S"))

    def set_connection_ok(self, ok: bool):
        self._conn_dot.set_ok(ok)
        self._conn_label.setText("已连接" if ok else "连接断开")
        color = "rgba(249,247,244,0.4)" if ok else "#F87171"
        self._conn_label.setStyleSheet(
            f"color: {color}; font-size: 11px;"
            "font-family: 'Segoe UI', sans-serif;"
        )


class MainWindow(QMainWindow):
    mustdo_complete = pyqtSignal()

    def __init__(self, config: Config, api: PersonalACApi, parent=None):
        super().__init__(parent)
        self.config = config
        self.api = api
        self._todo_total = 0
        self._todo_done = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.showFullScreen()

        self._setup_ui()
        self._setup_timers()
        self._load_initial_progress()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._top_bar = TopBar(self.config)
        layout.addWidget(self._top_bar)

        if HAS_WEBENGINE:
            self._web = QWebEngineView()
            settings = self._web.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

            page = self._web.page()
            page.setBackgroundColor(QColor("#F9F7F4"))

            self._web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self._web.load(QUrl(self.config.server_url))
            layout.addWidget(self._web, 1)
        else:
            placeholder = QLabel(f"无法加载 WebEngine\n请确认 PyQt6-WebEngine 已安装\n\n{self.config.server_url}")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                "background: #F9F7F4; color: #1A1815; font-size: 14px;"
                "font-family: 'Segoe UI', 'PingFang SC', sans-serif;"
            )
            layout.addWidget(placeholder, 1)

        self._bottom_bar = BottomBar()
        layout.addWidget(self._bottom_bar)

    def _setup_timers(self):
        self._mustdo_timer = QTimer(self)
        self._mustdo_timer.setInterval(30_000)
        self._mustdo_timer.timeout.connect(self._check_mustdo)
        self._mustdo_timer.start()

    def _load_initial_progress(self):
        QTimer.singleShot(2000, self._check_mustdo)

    def _check_mustdo(self):
        try:
            cfg = self.api.get_client_config()
            if not cfg:
                self.set_connection_status(False)
                return
            self.set_connection_status(True)
            done = cfg.get('must_do_done', 0)
            total = cfg.get('must_do_total', 0)
            self.update_progress(done, total)
            if cfg.get('mode') in ('pet', 'free'):
                self._mustdo_timer.stop()
                self.mustdo_complete.emit()
        except Exception:
            self.set_connection_status(False)

    def update_progress(self, done: int, total: int):
        self._todo_done = done
        self._todo_total = total
        self._top_bar.update_progress(done, total)

    def set_connection_status(self, ok: bool):
        self._top_bar.set_connection_ok(ok)
        self._bottom_bar.set_connection_ok(ok)

    def closeEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        blocked = {
            Qt.Key.Key_F4,
            Qt.Key.Key_Escape,
            Qt.Key.Key_Super_L,
            Qt.Key.Key_Super_R,
            Qt.Key.Key_Meta,
        }
        if event.key() in blocked:
            event.ignore()
            return
        mods = event.modifiers()
        alt = Qt.KeyboardModifier.AltModifier
        ctrl = Qt.KeyboardModifier.ControlModifier
        if (mods & alt and event.key() == Qt.Key.Key_F4):
            event.ignore()
            return
        if (mods & ctrl and mods & alt):
            event.ignore()
            return
        super().keyPressEvent(event)
