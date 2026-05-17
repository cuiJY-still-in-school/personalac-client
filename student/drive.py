"""云盘同步模块：监听本地文件夹 → 增量同步到服务器，并拉取服务器端修改"""

import base64
import hashlib
import logging
import mimetypes
import os
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SEC  = 60        # push 间隔
PULL_INTERVAL_SEC  = 30        # pull 间隔
MAX_FILE_SIZE      = 50 * 1024 * 1024  # 50 MB


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or 'application/octet-stream'


class DriveSync(QObject):
    status_changed = pyqtSignal(str)   # 状态文字更新

    def __init__(self, api, config, parent=None):
        super().__init__(parent)
        self._api    = api     # PersonalACApi
        self._config = config  # Config

        self._enabled   = self._config.drive_enabled
        self._path      = self._config.drive_path
        self._last_pull = self._config.drive_last_pull
        self._known: dict[str, str] = {}   # rel_path → checksum of last push

        self._push_timer = QTimer(self)
        self._push_timer.timeout.connect(self._push_tick)

        self._pull_timer = QTimer(self)
        self._pull_timer.timeout.connect(self._pull_tick)

        if self._enabled and self._path:
            self._start_timers()

    # ── public ────────────────────────────────────────────────────────────

    def configure(self, enabled: bool, path: str):
        self._enabled = enabled
        self._path    = path
        self._config.drive_enabled = enabled
        self._config.drive_path    = path
        self._config.save()
        self._stop_timers()
        if enabled and path and os.path.isdir(path):
            self._known.clear()
            self._start_timers()
            self.status_changed.emit(f'云盘同步已开启：{path}')
        else:
            self.status_changed.emit('云盘同步已关闭')

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> str:
        return self._path

    def force_push(self):
        threading.Thread(target=self._do_push, daemon=True).start()

    # ── timers ────────────────────────────────────────────────────────────

    def show_consent_if_needed(self):
        """首次启用时弹出知情确认弹窗，返回 True 表示用户同意"""
        dlg = QDialog()
        dlg.setWindowTitle('云盘同步 — 知情确认')
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel('☁️  允许 PersonalAC 同步文件吗？')
        title.setStyleSheet('font-size: 15px; font-weight: bold;')
        layout.addWidget(title)

        items = [
            '📂  你选择的文件夹内容会上传到家长的 PersonalAC 服务器',
            '👀  家长和 AI 老师可以查看、编辑这些文件',
            '🚫  请勿同步含密码、私钥等隐私信息的文件夹',
            '⚙️  你随时可以在托盘菜单「云盘设置」中关闭同步',
        ]
        for item in items:
            lbl = QLabel(item)
            lbl.setStyleSheet('color: #4A4540; font-size: 13px;')
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText('我已了解，同意开启')
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText('暂不开启')
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        return dlg.exec() == QDialog.DialogCode.Accepted

    def _start_timers(self):
        self._push_timer.start(SYNC_INTERVAL_SEC * 1000)
        self._pull_timer.start(PULL_INTERVAL_SEC * 1000)
        # 立即触发一次
        threading.Thread(target=self._do_push, daemon=True).start()
        threading.Thread(target=self._do_pull, daemon=True).start()

    def _stop_timers(self):
        self._push_timer.stop()
        self._pull_timer.stop()

    def _push_tick(self):
        threading.Thread(target=self._do_push, daemon=True).start()

    def _pull_tick(self):
        threading.Thread(target=self._do_pull, daemon=True).start()

    # ── push logic ────────────────────────────────────────────────────────

    def _do_push(self):
        root = self._path
        if not root or not os.path.isdir(root):
            return
        batch = []
        seen  = set()

        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                abs_p = os.path.join(dirpath, fname)
                rel   = os.path.relpath(abs_p, root).replace('\\', '/')
                seen.add(rel)
                try:
                    size = os.path.getsize(abs_p)
                    if size > MAX_FILE_SIZE:
                        continue
                    mtime = int(os.path.getmtime(abs_p) * 1000)
                    with open(abs_p, 'rb') as f:
                        data = f.read()
                    chk = _sha256(data)
                    if self._known.get(rel) == chk:
                        continue  # 未变化，跳过
                    batch.append({
                        'rel_path':    rel,
                        'name':        fname,
                        'content_b64': base64.b64encode(data).decode(),
                        'mime':        _guess_mime(abs_p),
                        'modify_time': mtime,
                        'checksum':    chk,
                    })
                    self._known[rel] = chk
                    if len(batch) >= 20:
                        self._send_batch(batch)
                        batch = []
                except OSError:
                    pass

        # 检查删除
        for rel in list(self._known):
            if rel not in seen:
                batch.append({'rel_path': rel, 'name': '', 'content_b64': '', 'checksum': '', 'modify_time': 0, 'deleted': True})
                del self._known[rel]

        if batch:
            self._send_batch(batch)

    def _send_batch(self, files: list):
        try:
            resp = self._api._post('/api/drive/sync', {'files': files})
            if resp and resp.get('success'):
                n = resp.get('data', {}).get('synced', 0)
                logger.info('Drive push: synced %d files', n)
                self.status_changed.emit(f'云盘：已同步 {n} 个文件')
        except Exception as e:
            logger.warning('Drive push failed: %s', e)

    # ── pull logic ────────────────────────────────────────────────────────

    def _do_pull(self):
        root = self._path
        if not root or not os.path.isdir(root):
            return
        try:
            resp = self._api._get('/api/drive/sync-pull', params={'since': self._last_pull})
            if not resp or not resp.get('success'):
                return
            changes = resp.get('data', {}).get('changes', [])
            for ch in changes:
                rel  = ch['rel_path']
                abs_p = os.path.normpath(os.path.join(root, rel))
                if not abs_p.startswith(os.path.normpath(root)):
                    continue  # path traversal guard
                if ch.get('deleted'):
                    try:
                        os.remove(abs_p)
                        logger.info('Drive pull: deleted %s', rel)
                    except OSError:
                        pass
                else:
                    content = ch.get('content', '')
                    os.makedirs(os.path.dirname(abs_p), exist_ok=True)
                    with open(abs_p, 'w', encoding='utf-8') as f:
                        f.write(content)
                    # 更新 known checksum 防止 push 立刻再上传
                    self._known[rel] = _sha256(content.encode('utf-8'))
                    logger.info('Drive pull: updated %s', rel)

            if changes:
                self._last_pull = int(time.time() * 1000)
                self._config.drive_last_pull = self._last_pull
                self._config.save()
                self.status_changed.emit(f'云盘：收到 {len(changes)} 个服务器更改')
        except Exception as e:
            logger.warning('Drive pull failed: %s', e)


# ── Settings Dialog ────────────────────────────────────────────────────────

class DriveSettingsDialog(QDialog):
    def __init__(self, drive_sync: DriveSync, parent=None):
        super().__init__(parent)
        self._sync = drive_sync
        self.setWindowTitle('云盘同步设置')
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # title
        title = QLabel('☁️  云盘同步')
        title.setStyleSheet('font-size: 16px; font-weight: bold; color: #1A1815;')
        layout.addWidget(title)

        desc = QLabel(
            '开启后，选定文件夹的内容将自动同步到服务器，\n'
            'AI 可以读写这些文件，家长可在网页云盘页面查看和编辑。'
        )
        desc.setStyleSheet('color: #6B6661; font-size: 13px; line-height: 1.6;')
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # enable toggle
        self._chk = QCheckBox('启用云盘同步')
        self._chk.setChecked(self._sync.enabled)
        self._chk.setStyleSheet('font-size: 14px; font-weight: 600;')
        layout.addWidget(self._chk)

        # path row
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit(self._sync.path)
        self._path_edit.setPlaceholderText('选择要同步的文件夹…')
        self._path_edit.setReadOnly(True)
        self._path_edit.setStyleSheet(
            'border: 1px solid #D4D0CA; border-radius: 7px; padding: 8px 12px; '
            'background: #F9F7F4; font-size: 13px;'
        )
        browse_btn = QPushButton('浏览…')
        browse_btn.setStyleSheet(
            'background: #E8E5E0; color: #333; border: none; border-radius: 7px; '
            'padding: 8px 16px; font-size: 13px; font-weight: 600;'
        )
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # status
        self._status_label = QLabel('')
        self._status_label.setStyleSheet('color: #9A9690; font-size: 12px;')
        layout.addWidget(self._status_label)
        self._sync.status_changed.connect(self._status_label.setText)

        # warn
        warn = QLabel('⚠️  不要同步包含密码、私钥等敏感信息的文件夹。')
        warn.setStyleSheet('color: #C08040; font-size: 12px; background: #FEF9F0; '
                           'border: 1px solid #F0D9A0; border-radius: 6px; padding: 8px;')
        warn.setWordWrap(True)
        layout.addWidget(warn)

        # buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._apply)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, '选择同步文件夹', self._path_edit.text() or os.path.expanduser('~'))
        if folder:
            self._path_edit.setText(folder)

    def _apply(self):
        enabled = self._chk.isChecked()
        path    = self._path_edit.text().strip()
        if enabled and not path:
            self._status_label.setText('请先选择同步文件夹')
            return
        # 首次开启需知情确认
        if enabled and not self._sync.enabled:
            if not self._sync.show_consent_if_needed():
                self._chk.setChecked(False)
                return
        self._sync.configure(enabled, path)
        self.accept()
