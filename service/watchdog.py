import logging
import os
import sys
import time

logger = logging.getLogger(__name__)

_SERVICE_NAME = "PersonalACWatchdog"
_STUDENT_EXE = "personalac-student.exe"
_CHECK_INTERVAL = 30


def _is_student_running() -> bool:
    try:
        import psutil
        for proc in psutil.process_iter(["name", "cmdline"]):
            name = proc.info.get("name", "") or ""
            if name.lower() == _STUDENT_EXE.lower():
                return True
            cmdline = proc.info.get("cmdline") or []
            if any("personalac" in str(arg).lower() and "student" in str(arg).lower() for arg in cmdline):
                return True
    except Exception as e:
        logger.debug("process check error: %s", e)
    return False


def _launch_student():
    exe_dir = os.path.dirname(sys.executable)
    exe_path = os.path.join(exe_dir, _STUDENT_EXE)
    if not os.path.exists(exe_path):
        exe_path = _STUDENT_EXE
    try:
        import subprocess
        subprocess.Popen([exe_path], close_fds=True)
        logger.info("Launched student agent: %s", exe_path)
    except Exception as e:
        logger.error("Failed to launch student agent: %s", e)


if sys.platform == "win32":
    try:
        import win32service
        import win32serviceutil
        import win32event
        import servicemanager

        class PersonalACWatchdog(win32serviceutil.ServiceFramework):
            _svc_name_ = _SERVICE_NAME
            _svc_display_name_ = "PersonalAC Watchdog"
            _svc_description_ = "Keeps the PersonalAC student agent running."

            def __init__(self, args):
                win32serviceutil.ServiceFramework.__init__(self, args)
                self._stop_event = win32event.CreateEvent(None, 0, 0, None)
                self._running = False

            def SvcStop(self):
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                self._running = False
                win32event.SetEvent(self._stop_event)

            def SvcDoRun(self):
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, ""),
                )
                self._running = True
                self._run_loop()

            def _run_loop(self):
                while self._running:
                    if not _is_student_running():
                        servicemanager.LogInfoMsg(
                            f"{_SERVICE_NAME}: student agent not found, relaunching..."
                        )
                        _launch_student()
                    result = win32event.WaitForSingleObject(
                        self._stop_event, _CHECK_INTERVAL * 1000
                    )
                    if result == win32event.WAIT_OBJECT_0:
                        break

            @classmethod
            def install(cls):
                win32serviceutil.InstallService(
                    cls._svc_reg_class_,
                    cls._svc_name_,
                    cls._svc_display_name_,
                    startType=win32service.SERVICE_AUTO_START,
                )
                print(f"Service '{cls._svc_name_}' installed.")

            @classmethod
            def uninstall(cls):
                win32serviceutil.RemoveService(cls._svc_name_)
                print(f"Service '{cls._svc_name_}' removed.")

    except ImportError:
        class PersonalACWatchdog:
            @classmethod
            def install(cls):
                print("pywin32 not available; cannot install service")

            @classmethod
            def uninstall(cls):
                print("pywin32 not available; cannot remove service")

else:
    class PersonalACWatchdog:
        """Non-Windows stub — runs a simple loop for dev/testing."""

        _running = False

        def start(self):
            print(f"[{_SERVICE_NAME}] Starting watchdog loop (non-Windows mode)")
            self._running = True
            try:
                while self._running:
                    if not _is_student_running():
                        print(f"[{_SERVICE_NAME}] Student agent not running, would relaunch")
                    time.sleep(_CHECK_INTERVAL)
            except KeyboardInterrupt:
                self._running = False

        def stop(self):
            self._running = False

        @classmethod
        def install(cls):
            print(f"[{_SERVICE_NAME}] Windows service installation not supported on this platform")

        @classmethod
        def uninstall(cls):
            print(f"[{_SERVICE_NAME}] Windows service removal not supported on this platform")


def main():
    if sys.platform == "win32":
        if len(sys.argv) > 1 and sys.argv[1] in ("install", "uninstall", "start", "stop", "restart"):
            win32serviceutil.HandleCommandLine(PersonalACWatchdog)
        else:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(PersonalACWatchdog)
            servicemanager.StartServiceCtrlDispatcher()
    else:
        watchdog = PersonalACWatchdog()
        watchdog.start()


if __name__ == "__main__":
    main()
