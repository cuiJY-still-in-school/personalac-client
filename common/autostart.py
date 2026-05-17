"""开机自启注册 / 注销（支持 Windows 和 macOS）"""
import logging
import os
import sys

logger = logging.getLogger(__name__)

APP_NAME = "PersonalAC"
_PLIST_PATH = os.path.expanduser("~/Library/LaunchAgents/com.personalac.student.plist")
_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _exe_cmd() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable,)
    return (sys.executable, os.path.abspath(sys.argv[0]))


def is_enabled() -> bool:
    try:
        if sys.platform == "win32":
            return _win_is_enabled()
        if sys.platform == "darwin":
            return os.path.exists(_PLIST_PATH)
    except Exception:
        pass
    return False


def enable() -> bool:
    try:
        if sys.platform == "win32":
            _win_enable()
        elif sys.platform == "darwin":
            _mac_enable()
        logger.info("autostart enabled")
        return True
    except Exception as e:
        logger.warning("autostart enable failed: %s", e)
        return False


def disable() -> bool:
    try:
        if sys.platform == "win32":
            _win_disable()
        elif sys.platform == "darwin":
            _mac_disable()
        logger.info("autostart disabled")
        return True
    except Exception as e:
        logger.warning("autostart disable failed: %s", e)
        return False


# ── Windows ──────────────────────────────────────────────────────────────────

def _win_is_enabled() -> bool:
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def _win_enable():
    import winreg
    cmd = " ".join(f'"{p}"' for p in _exe_cmd())
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
    winreg.CloseKey(key)


def _win_disable():
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except OSError:
        pass


# ── macOS ─────────────────────────────────────────────────────────────────────

def _mac_enable():
    import subprocess
    args = "".join(f"    <string>{p}</string>\n" for p in _exe_cmd())
    log_dir = os.path.expanduser("~/Library/Logs/PersonalAC")
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.personalac.student</string>
  <key>ProgramArguments</key>
  <array>
{args}  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
  <key>StandardOutPath</key><string>{log_dir}/student.log</string>
  <key>StandardErrorPath</key><string>{log_dir}/student.log</string>
</dict>
</plist>"""
    os.makedirs(os.path.dirname(_PLIST_PATH), exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    with open(_PLIST_PATH, "w") as f:
        f.write(plist)
    subprocess.run(["launchctl", "load", _PLIST_PATH], capture_output=True)


def _mac_disable():
    import subprocess
    if os.path.exists(_PLIST_PATH):
        subprocess.run(["launchctl", "unload", _PLIST_PATH], capture_output=True)
        os.remove(_PLIST_PATH)


