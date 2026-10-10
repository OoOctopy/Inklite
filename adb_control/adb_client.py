"""Small subprocess wrapper. No shell interpolation; every command targets one serial."""
import re
import subprocess
from .config import COMPONENT_RE, valid_package


class AdbError(RuntimeError):
    pass


class AdbClient:
    def __init__(self, executable="adb", serial=None, timeout=10.0):
        self.executable = executable
        self.requested_serial = serial
        self.serial = None
        self.timeout = timeout

    def _run(self, args):
        try:
            result = subprocess.run([self.executable, *args], capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=self.timeout)
        except FileNotFoundError as exc:
            raise AdbError("ADB not installed/found. Install Platform Tools and set ADB_PATH or PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB timed out after {self.timeout}s") from exc
        except OSError as exc:
            raise AdbError(f"Could not run ADB: {exc}") from exc
        output = result.stdout.strip()
        combined = output + "\n" + result.stderr.strip()
        # Some Android shell services print errors while returning exit code zero.
        if result.returncode or re.search(r"(?im)^\s*(?:error\b|exception\b|securityexception\b|java\.[\w.]*exception\b)", combined):
            raise AdbError(combined.strip() or f"ADB exited with code {result.returncode}")
        return output

    def connect(self):
        self.serial = None
        output = self._run(["devices"])
        devices = {}
        for line in output.splitlines():
            columns = line.split()
            if len(columns) >= 2 and columns[1] in {"device", "offline", "unauthorized", "no"}:
                devices[columns[0]] = columns[1]
        if self.requested_serial:
            state = devices.get(self.requested_serial)
            if state != "device":
                raise AdbError(f"Device {self.requested_serial}: {state or 'not connected'}. Check USB debugging authorization.")
            self.serial = self.requested_serial
        else:
            if not devices:
                raise AdbError("No Android device connected. Connect USB and enable USB debugging.")
            if len(devices) != 1:
                raise AdbError("Multiple Android devices detected. Set DEVICE_SERIAL or use --serial.")
            serial, state = next(iter(devices.items()))
            if state != "device":
                raise AdbError(f"Device {serial} is {state}. Unlock phone and authorize USB debugging.")
            self.serial = serial
        return self.serial

    def shell(self, *args):
        if not self.serial:
            raise AdbError("No selected device; call connect() first")
        return self._run(["-s", self.serial, "shell", *args])

    def validate_activity(self, component, user):
        if not COMPONENT_RE.fullmatch(component):
            raise ValueError("Invalid activity component")
        output = self.shell("cmd", "package", "resolve-activity", "--brief", "--user", str(user), "-n", component)
        if not any(COMPONENT_RE.fullmatch(line.strip()) for line in output.splitlines()):
            raise AdbError(f"Redirect activity cannot be resolved for user {user}: {component}. Install/configure it before --enforce.")

    def force_stop(self, package, user):
        if not valid_package(package):
            raise ValueError("Invalid package name")
        self.shell("am", "force-stop", "--user", str(user), package)

    def start_activity(self, component, user):
        if not COMPONENT_RE.fullmatch(component):
            raise ValueError("Invalid activity component")
        self.shell("am", "start", "--user", str(user), "-n", component)
