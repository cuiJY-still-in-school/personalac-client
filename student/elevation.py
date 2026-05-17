"""Windows UAC 管理员权限提升"""
import logging
import sys

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    if sys.platform != "win32":
        return True  # macOS doesn't need UAC
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def request_elevation() -> bool:
    """以管理员身份重启当前进程，返回 True 表示已触发重启（当前进程应退出）。"""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = ""
        else:
            exe = sys.executable
            params = " ".join(f'"{a}"' for a in sys.argv)

        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, None, 1
        )
        # ShellExecuteW returns > 32 on success
        if ret > 32:
            logger.info("Re-launching as administrator")
            return True
        else:
            logger.warning("ShellExecuteW runas returned %s", ret)
            return False
    except Exception as e:
        logger.warning("request_elevation failed: %s", e)
        return False


def ensure_admin_or_warn(parent_widget=None) -> bool:
    """检查是否为管理员；若不是，弹出对话框请求提升并重启。
    返回 True 表示已是管理员（可继续运行），False 表示已触发重启（当前进程应立即退出）。
    """
    if sys.platform != "win32":
        return True
    if is_admin():
        return True

    from PyQt6.QtWidgets import QMessageBox
    msg = QMessageBox(parent_widget)
    msg.setWindowTitle("需要管理员权限")
    msg.setText(
        "PersonalAC 需要管理员权限才能完整监控应用使用情况并拦截违禁程序。\n\n"
        "点击「以管理员运行」将弹出 Windows 安全提示，请选择「是」继续。"
    )
    msg.setIcon(QMessageBox.Icon.Warning)
    run_btn = msg.addButton("以管理员运行", QMessageBox.ButtonRole.AcceptRole)
    msg.addButton("稍后再说", QMessageBox.ButtonRole.RejectRole)
    msg.exec()

    if msg.clickedButton() == run_btn:
        elevated = request_elevation()
        if elevated:
            return False  # caller should sys.exit(0)

    return True  # user declined or elevation failed — continue without admin
