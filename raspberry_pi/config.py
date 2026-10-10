from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from uuid import UUID

DEFAULT_CONFIG = Path(__file__).with_name("config.json")
APPLICATION_PATH = "/com/inklite/application"
ADVERTISEMENT_PATH = "/com/inklite/advertisement0"


@dataclass(frozen=True)
class Config:
    adapter: str
    advertising_name: str
    service_uuid: str
    command_uuid: str
    register_timeout: float
    pages: tuple[str, ...]
    timer_minutes: int
    display_mode: str
    width: int
    height: int
    rotation: int
    assets_path: Path
    mock_output_dir: Path
    driver_path: Path
    driver_module: str
    min_refresh_interval: float
    busy_timeout: float
    shutdown_timeout: float


def load_config(path=DEFAULT_CONFIG):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    keys = {"ADAPTER", "ADVERTISING_NAME", "SERVICE_UUID", "COMMAND_CHARACTERISTIC_UUID", "REGISTER_TIMEOUT",
            "PAGES", "TIMER_MINUTES", "DISPLAY_MODE", "WIDTH", "HEIGHT", "ROTATION", "ASSETS_PATH",
            "MOCK_OUTPUT_DIR", "DRIVER_PATH", "DRIVER_MODULE", "MIN_REFRESH_INTERVAL", "BUSY_TIMEOUT", "SHUTDOWN_TIMEOUT"}
    if not isinstance(data, dict) or set(data) != keys:
        raise ValueError("Pi config must contain exactly: " + ", ".join(sorted(keys)))
    adapter = data["ADAPTER"]
    if not isinstance(adapter, str) or not re.fullmatch(r"hci\d+", adapter):
        raise ValueError("ADAPTER must name a BlueZ adapter, such as hci0")
    name = data["ADVERTISING_NAME"]
    # One custom 128-bit service UUID + flags + an 8-byte name fits legacy 31-byte advertising.
    if not isinstance(name, str) or not 1 <= len(name.encode("utf-8")) <= 8 or not name.isprintable():
        raise ValueError("ADVERTISING_NAME must contain 1–8 printable UTF-8 bytes")
    if not all(isinstance(data[key], str) for key in ("SERVICE_UUID", "COMMAND_CHARACTERISTIC_UUID")):
        raise ValueError("UUID settings must be strings")
    service = str(UUID(data["SERVICE_UUID"]))
    command = str(UUID(data["COMMAND_CHARACTERISTIC_UUID"]))
    if service == command:
        raise ValueError("Service UUID and command characteristic UUID must differ")
    timeout = data["REGISTER_TIMEOUT"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("REGISTER_TIMEOUT must be a positive finite number")
    pages = data["PAGES"]
    if not isinstance(pages, list) or not pages or len(pages) > 8 or not all(
        isinstance(page, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,31}", page) for page in pages
    ) or len(set(pages)) != len(pages):
        raise ValueError("PAGES must contain 1–8 distinct lower-case page identifiers")
    for key in ("WIDTH", "HEIGHT", "TIMER_MINUTES"):
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 4096:
            raise ValueError(f"{key} must be an integer from 1 to 4096")
    if not isinstance(data["DISPLAY_MODE"], str) or data["DISPLAY_MODE"] not in {"mock", "hardware"}:
        raise ValueError("DISPLAY_MODE must be mock or hardware")
    if isinstance(data["ROTATION"], bool) or data["ROTATION"] not in (0, 90, 180, 270):
        raise ValueError("ROTATION must be 0, 90, 180 or 270")
    for key in ("MIN_REFRESH_INTERVAL", "BUSY_TIMEOUT", "SHUTDOWN_TIMEOUT"):
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be a finite nonnegative number")
    if data["BUSY_TIMEOUT"] == 0 or data["SHUTDOWN_TIMEOUT"] == 0:
        raise ValueError("Busy/shutdown timeouts must be positive")
    paths = []
    for key in ("ASSETS_PATH", "MOCK_OUTPUT_DIR", "DRIVER_PATH"):
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a nonempty path")
        paths.append((path.parent / value).resolve())
    module = data["DRIVER_MODULE"]
    if not isinstance(module, str) or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", module):
        raise ValueError("DRIVER_MODULE must be a Python module name")
    return Config(adapter, name, service, command, float(timeout), tuple(pages), data["TIMER_MINUTES"],
                  data["DISPLAY_MODE"], data["WIDTH"], data["HEIGHT"], data["ROTATION"], *paths, module,
                  float(data["MIN_REFRESH_INTERVAL"]), float(data["BUSY_TIMEOUT"]), float(data["SHUTDOWN_TIMEOUT"]))
