"""定时截图并上传到服务端"""
import base64
import logging
from io import BytesIO

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap

logger = logging.getLogger(__name__)

_INTERVAL_MS = 10 * 60 * 1000  # 10 minutes (default; overridden by server config)
_MAX_SIDE = 1280                # resize if wider/taller than this
_JPEG_QUALITY = 45


class ScreenshotUploader(QObject):
    upload_failed = pyqtSignal(str)

    def __init__(self, api, interval_ms: int = _INTERVAL_MS, parent=None):
        super().__init__(parent)
        self._api = api
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._capture_and_upload)

    def set_interval(self, interval_ms: int):
        was_active = self._timer.isActive()
        self._timer.setInterval(interval_ms)
        if was_active:
            self._timer.start()

    def start(self):
        self._timer.start()
        logger.info("Screenshot uploader started (interval=%ds)", self._timer.interval() // 1000)

    def stop(self):
        self._timer.stop()

    def _capture_and_upload(self):
        try:
            data = self._capture_b64()
        except Exception as e:
            logger.warning("Screenshot capture failed: %s", e)
            return
        try:
            ok = self._api.upload_screenshot(data)
            if not ok:
                logger.debug("Screenshot upload returned failure")
        except Exception as e:
            logger.warning("Screenshot upload error: %s", e)

    def _capture_b64(self) -> str:
        screen = QApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("No primary screen")
        pixmap: QPixmap = screen.grabWindow(0)

        # Downscale if needed
        if pixmap.width() > _MAX_SIDE or pixmap.height() > _MAX_SIDE:
            pixmap = pixmap.scaled(
                _MAX_SIDE, _MAX_SIDE,
                aspectRatioMode=1,           # Qt.AspectRatioMode.KeepAspectRatio
                transformMode=1,             # Qt.TransformationMode.SmoothTransformation
            )

        buf = BytesIO()
        ba = pixmap.toImage()
        # Save via Qt to bytes
        from PyQt6.QtCore import QBuffer, QIODevice
        qbuf = QBuffer()
        qbuf.open(QIODevice.OpenMode.WriteOnly)
        pixmap.save(qbuf, "JPEG", _JPEG_QUALITY)
        raw = bytes(qbuf.data())
        qbuf.close()

        return base64.b64encode(raw).decode()
