"""Load explicit JSON settings; relative paths resolve beside the config file."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

DEFAULT_CONFIG = Path(__file__).with_name("config.json")
PACKAGE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")
COMPONENT_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+)/([.A-Za-z_][A-Za-z0-9_.$]*)")


def valid_package(value):
    return isinstance(value, str) and PACKAGE_RE.fullmatch(value) is not None


@dataclass(frozen=True)
class Config:
    adb_path: str
    serial: str | None
    inklite_package: str
    inklite_activity: str
    interval: float
    timeout: float
    retry_interval: float
    block_cooldown: float
    whitelist_path: Path


def load_config(path=DEFAULT_CONFIG):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")
    allowed = {"ADB_PATH", "DEVICE_SERIAL", "INKLITE_PACKAGE", "INKLITE_ACTIVITY",
               "CHECK_INTERVAL", "ADB_TIMEOUT", "RETRY_INTERVAL", "BLOCK_COOLDOWN", "WHITELIST_PATH"}
    if set(data) - allowed:
        raise ValueError(f"Unknown config settings: {sorted(set(data) - allowed)}")
    package = data["INKLITE_PACKAGE"]
    activity = data["INKLITE_ACTIVITY"]
    component = COMPONENT_RE.fullmatch(activity) if isinstance(activity, str) else None
    if not valid_package(package) or not component or component[1] != package:
        raise ValueError("INKLITE_ACTIVITY must be package/activity in INKLITE_PACKAGE")
    numbers = []
    for key in ("CHECK_INTERVAL", "ADB_TIMEOUT", "RETRY_INTERVAL", "BLOCK_COOLDOWN"):
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be a positive finite number")
        numbers.append(float(value))
    serial = data.get("DEVICE_SERIAL")
    if serial is not None and (not isinstance(serial, str) or not serial.strip()):
        raise ValueError("DEVICE_SERIAL must be null or a nonempty string")
    adb = data["ADB_PATH"]
    if not isinstance(adb, str) or not adb.strip():
        raise ValueError("ADB_PATH must name adb or an executable path")
    # A bare executable name is looked up on PATH; explicit relative paths use the config directory.
    if not Path(adb).is_absolute() and ("/" in adb or "\\" in adb):
        adb = str(path.parent / adb)
    whitelist = data["WHITELIST_PATH"]
    if not isinstance(whitelist, str) or not whitelist.strip():
        raise ValueError("WHITELIST_PATH must be a nonempty path")
    return Config(adb, serial, package, activity, *numbers, path.parent / whitelist)


def load_whitelist(path, inklite_package):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, list) or not all(valid_package(item) for item in data):
        raise ValueError("Whitelist must be a JSON array of valid package names")
    # Never force-stop the redirect target, even if accidentally omitted from JSON.
    return frozenset(data) | {inklite_package}
