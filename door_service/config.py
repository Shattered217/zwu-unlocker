import json
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from door_service.constants import (
    DEFAULT_CALLBACK_PATH,
    DEFAULT_CONFIG_FILE,
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_HEALTH_INTERVAL,
    DEFAULT_STATE_FILE,
)


def detect_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def config_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def config_int(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def config_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def normalize_path(path: str) -> str:
    return path if path.startswith("/") else "/" + path


def join_path(base_path: str, suffix: str) -> str:
    base = normalize_path(base_path).rstrip("/")
    tail = suffix if suffix.startswith("/") else "/" + suffix
    return base + tail


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass(frozen=True)
class RoutesConfig:
    base_path: str
    callback_path: str
    dashboard_path: str
    status_path: str
    refresh_path: str
    refresh_start_path: str
    open_api_path: str
    check_api_path: str


@dataclass(frozen=True)
class ServiceConfig:
    host: str
    port: int
    public_base: str
    callback_url: str
    state_file: Path
    exchange_token: bool
    access_key: str | None
    default_door_code: str | None
    health_interval: int
    telegram: TelegramConfig
    routes: RoutesConfig


def default_config_path() -> Path:
    return Path(DEFAULT_CONFIG_FILE)


def build_public_base(host: str, port: int, configured_public_base: str | None) -> str:
    if configured_public_base:
        return configured_public_base.rstrip("/")
    return f"http://{detect_lan_ip()}:{port}"


def build_callback_url(public_base: str, configured_callback_url: str | None, callback_path: str) -> str:
    if configured_callback_url:
        return configured_callback_url.rstrip("/")
    return public_base.rstrip("/") + callback_path


def load_config(config_file: Path) -> ServiceConfig:
    if not config_file.exists():
        raise FileNotFoundError(f"config file not found: {config_file}")

    raw = json.loads(config_file.read_text(encoding="utf-8"))
    host = raw.get("host", "0.0.0.0")
    port = config_int(raw.get("port"), 8765)
    public_base = build_public_base(host, port, raw.get("public_base"))

    routes_raw = raw.get("routes", {}) if isinstance(raw.get("routes"), dict) else {}
    base_path = normalize_path(routes_raw.get("base_path", DEFAULT_DASHBOARD_PATH))
    callback_path = normalize_path(routes_raw.get("callback_path", DEFAULT_CALLBACK_PATH))
    routes = RoutesConfig(
        base_path=base_path,
        callback_path=callback_path,
        dashboard_path=base_path,
        status_path=join_path(base_path, "/status"),
        refresh_path=join_path(base_path, "/refresh"),
        refresh_start_path=join_path(base_path, "/refresh/start"),
        open_api_path=join_path(base_path, "/api/open"),
        check_api_path=join_path(base_path, "/api/check"),
    )

    telegram_raw = raw.get("telegram", {}) if isinstance(raw.get("telegram"), dict) else {}
    telegram = TelegramConfig(
        bot_token=config_str(telegram_raw.get("bot_token")),
        chat_id=config_str(telegram_raw.get("chat_id")),
    )

    return ServiceConfig(
        host=host,
        port=port,
        public_base=public_base,
        callback_url=build_callback_url(public_base, raw.get("callback_url"), callback_path),
        state_file=Path(raw.get("state_file", DEFAULT_STATE_FILE)),
        exchange_token=config_bool(raw.get("exchange_token"), True),
        access_key=raw.get("access_key"),
        default_door_code=raw.get("default_door_code"),
        health_interval=config_int(raw.get("health_interval"), DEFAULT_HEALTH_INTERVAL),
        telegram=telegram,
        routes=routes,
    )
